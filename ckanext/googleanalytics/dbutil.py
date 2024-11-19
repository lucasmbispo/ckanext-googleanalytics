from sqlalchemy import Table, Column, Integer, String, MetaData, Float, DateTime
from sqlalchemy.sql import select, text
from sqlalchemy import func
import logging
import ckan.model as model

log = logging.getLogger(__name__)
# from ckan.model.authz import PSEUDO_USER__VISITOR
from ckan.lib.base import *

cached_tables = {}


def init_tables():
    metadata = MetaData()
    package_stats = Table(
        "package_stats",
        metadata,
        Column("package_id", String(60), primary_key=True),
        Column("visits_recently", Integer),
        Column("visits_ever", Integer),
    )
    resource_stats = Table(
        "resource_stats",
        metadata,
        Column("resource_id", String(60), primary_key=True),
        Column("visits_recently", Integer),
        Column("visits_ever", Integer),
    )
    frontend_stats = Table(
        "frontend_stats",
        metadata,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("resource_id", String(60), primary_key=True),
        Column("dataset_id", String(60), nullable=False),      
        Column("count", Integer),              
        Column("language", String(2), nullable=False),   #AR or EN
        Column("dataset_title", String(60)),
        Column("date_created", DateTime)
    )
    metadata.create_all(model.meta.engine)


def get_table(name):
    if name not in cached_tables:
        meta = MetaData()
        meta.reflect(bind=model.meta.engine)
        table = meta.tables[name]
        cached_tables[name] = table
    return cached_tables[name]


def _update_visits(table_name, item_id, recently, ever):
    stats = get_table(table_name)
    id_col_name = "%s_id" % table_name[: -len("_stats")]
    id_col = getattr(stats.c, id_col_name)
    s = select([func.count(id_col)], id_col == item_id)
    connection = model.Session.connection()
    count = connection.execute(s).fetchone()
    if count and count[0]:
        connection.execute(
            stats.update()
            .where(id_col == item_id)
            .values(visits_recently=recently, visits_ever=ever)
        )
    else:
        values = {
            id_col_name: item_id,
            "visits_recently": recently,
            "visits_ever": ever,
        }
        connection.execute(stats.insert().values(**values))

def update_frontend_stats(stats):
    table = get_table('frontend_stats')
    session = model.Session()
    try:
        for stat in stats:
            session.execute(table.insert().values(**stat))  
        session.commit()  
        log.info("Data inserted, transaction committed.")
    except Exception as e:
        log.error("Error during insertion: %s", str(e))
        session.rollback() 
    finally:
        session.close()  
    
def update_resource_visits(resource_id, recently, ever):
    return _update_visits("resource_stats", resource_id, recently, ever)


def update_package_visits(package_id, recently, ever):
    return _update_visits("package_stats", package_id, recently, ever)


def get_resource_visits_for_url(url):
    connection = model.Session.connection()
    count = connection.execute(
        text(
            """SELECT visits_ever FROM resource_stats, resource
        WHERE resource_id = resource.id
        AND resource.url = :url"""
        ),
        url=url,
    ).fetchone()
    return count and count[0] or ""


""" get_top_packages is broken, and needs to be rewritten to work with
CKAN 2.*. This is because ckan.authz has been removed in CKAN 2.*

See commit ffa86c010d5d25fa1881c6b915e48f3b44657612
"""


def get_top_packages(limit=20):
    items = []
    # caveat emptor: the query below will not filter out private
    # or deleted datasets (TODO)
    q = model.Session.query(model.Package)
    connection = model.Session.connection()
    package_stats = get_table("package_stats")
    s = select(
        [
            package_stats.c.package_id,
            package_stats.c.visits_recently,
            package_stats.c.visits_ever,
        ]
    ).order_by(package_stats.c.visits_recently.desc())
    res = connection.execute(s).fetchmany(limit)
    for package_id, recent, ever in res:
        item = q.filter(text("package.id = '%s'" % package_id))
        if not item.count():
            continue
        items.append((item.first(), recent, ever))
    return items


def get_top_resources(limit=20):
    items = []
    connection = model.Session.connection()
    resource_stats = get_table("resource_stats")
    s = select(
        [
            resource_stats.c.resource_id,
            resource_stats.c.visits_recently,
            resource_stats.c.visits_ever,
        ]
    ).order_by(resource_stats.c.visits_recently.desc())
    res = connection.execute(s).fetchmany(limit)
    for resource_id, recent, ever in res:
        item = model.Session.query(model.Resource).filter(
            "resource.id = '%s'" % resource_id
        )
        if not item.count():
            continue
        items.append((item.first(), recent, ever))
    return items


def get_resource_stat(resource_id):
    connection = model.Session.connection()
    resource_stats = get_table("resource_stats")
    s = select(
        [resource_stats.c.visits_ever]
    ).where(resource_stats.c.resource_id == resource_id)
    res = connection.execute(s).fetchone()
    return res

def get_package_stat(package_id):
    connection = model.Session.connection()
    package_stats = get_table("frontend_stats")
    s = select(
        [package_stats.c.count]
    ).where(package_stats.c.dataset_id == package_id)
    res = connection.execute(s).fetchone()
    return res
    