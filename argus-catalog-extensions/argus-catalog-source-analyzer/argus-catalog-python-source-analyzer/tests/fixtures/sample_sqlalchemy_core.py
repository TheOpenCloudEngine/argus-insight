from sqlalchemy import MetaData, Table, Column, Integer, String, create_engine, text, select, insert, update, delete

metadata = MetaData()

products = Table(
    "products", metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String(100)),
    Column("price", Integer),
)

categories = Table(
    "categories", metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String(50)),
)


def get_all_products(connection):
    stmt = select(products)
    return connection.execute(stmt).fetchall()


def insert_product(connection, name, price):
    stmt = insert(products).values(name=name, price=price)
    connection.execute(stmt)


def update_price(connection, product_id, new_price):
    stmt = update(products).where(products.c.id == product_id).values(price=new_price)
    connection.execute(stmt)


def delete_product(connection, product_id):
    stmt = delete(products).where(products.c.id == product_id)
    connection.execute(stmt)


def raw_query(connection):
    result = connection.execute(text("SELECT p.name, c.name FROM products p JOIN categories c ON p.category_id = c.id"))
    return result.fetchall()
