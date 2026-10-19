import os
import sqlite3
import numpy as np
import pandas as pd


# Генерація даних
def generate_raw_data(n_rows=1_000_000):
    print("Генерація  даних")
    np.random.seed(42)
    categories = ["Groceries", "Electronics", "Clothing", "Travel", "Utilities"]
    cities = ["Kyiv", "Lviv", "Odesa", "Kharkiv", "Dnipro"]

    user_ids = np.random.randint(1000, 2000, size=n_rows)
    product_ids = np.random.randint(100, 500, size=n_rows)

    user_cities = [cities[uid % len(cities)] for uid in user_ids]
    product_categories = [
        categories[pid % len(categories)] for pid in product_ids
    ]

    df = pd.DataFrame(
        {
            "transaction_id": range(1, n_rows + 1),
            "user_id": user_ids,
            "user_city": user_cities,
            "product_id": product_ids,
            "category_name": product_categories,
            "amount": np.round(np.random.uniform(1.0, 5000.0, size=n_rows), 2),
            "timestamp": pd.date_range(
                start="2026-01-01", periods=n_rows, freq="s"
            ),
        }
    )
    return df


#  Схема "Зірка"
def build_star_schema(conn, df_raw):
    cursor = conn.cursor()

    cursor.execute(
        """
    CREATE TABLE dim_user (
        user_id INTEGER PRIMARY KEY,
        city TEXT
    )"""
    )

    cursor.execute(
        """
    CREATE TABLE dim_product (
        product_id INTEGER PRIMARY KEY,
        category_name TEXT
    )"""
    )

    cursor.execute(
        """
    CREATE TABLE dim_date (
        date_id TEXT PRIMARY KEY,
        year INTEGER,
        month INTEGER,
        day INTEGER,
        hour INTEGER
    )"""
    )

    cursor.execute(
        """
    CREATE TABLE fact_sales (
        transaction_id INTEGER PRIMARY KEY,
        user_id INTEGER,
        product_id INTEGER,
        date_id TEXT,
        amount REAL,
        FOREIGN KEY (user_id) REFERENCES dim_user(user_id),
        FOREIGN KEY (product_id) REFERENCES dim_product(product_id),
        FOREIGN KEY (date_id) REFERENCES dim_date(date_id)
    )"""
    )

    # Виміри
    dim_user = df_raw[["user_id", "user_city"]].drop_duplicates(
        subset=["user_id"]
    )
    dim_user.columns = ["user_id", "city"]

    dim_product = df_raw[["product_id", "category_name"]].drop_duplicates(
        subset=["product_id"]
    )

    df_raw["date_id"] = df_raw["timestamp"].dt.strftime("%Y-%m-%d %H:00:00")
    dim_date = pd.DataFrame({"date_id": df_raw["date_id"].unique()})
    dt_series = pd.to_datetime(dim_date["date_id"])
    dim_date["year"] = dt_series.dt.year
    dim_date["month"] = dt_series.dt.month
    dim_date["day"] = dt_series.dt.day
    dim_date["hour"] = dt_series.dt.hour

    dim_user.to_sql("dim_user", conn, if_exists="append", index=False)
    dim_product.to_sql("dim_product", conn, if_exists="append", index=False)
    dim_date.to_sql("dim_date", conn, if_exists="append", index=False)

    # Факти
    fact_sales = df_raw[
        ["transaction_id", "user_id", "product_id", "date_id", "amount"]
    ]
    fact_sales.to_sql("fact_sales", conn, if_exists="append", index=False)
    conn.commit()


#  Схема "Сніжинка"
def build_snowflake_schema(conn, df_raw):
    cursor = conn.cursor()

    cursor.execute(
        """
    CREATE TABLE dim_category (
        category_id INTEGER PRIMARY KEY AUTOINCREMENT,
        category_name TEXT UNIQUE
    )"""
    )

    cursor.execute(
        """
    CREATE TABLE dim_user (
        user_id INTEGER PRIMARY KEY,
        city TEXT
    )"""
    )

    cursor.execute(
        """
    CREATE TABLE dim_product (
        product_id INTEGER PRIMARY KEY,
        category_id INTEGER,
        FOREIGN KEY (category_id) REFERENCES dim_category(category_id)
    )"""
    )

    cursor.execute(
        """
    CREATE TABLE dim_date (
        date_id TEXT PRIMARY KEY,
        year INTEGER,
        month INTEGER,
        day INTEGER,
        hour INTEGER
    )"""
    )

    cursor.execute(
        """
    CREATE TABLE fact_sales (
        transaction_id INTEGER PRIMARY KEY,
        user_id INTEGER,
        product_id INTEGER,
        date_id TEXT,
        amount REAL,
        FOREIGN KEY (user_id) REFERENCES dim_user(user_id),
        FOREIGN KEY (product_id) REFERENCES dim_product(product_id),
        FOREIGN KEY (date_id) REFERENCES dim_date(date_id)
    )"""
    )

    # Заповнення категорій
    categories = pd.DataFrame(
        {"category_name": df_raw["category_name"].unique()}
    )
    categories.to_sql("dim_category", conn, if_exists="append", index=False)

    cat_lookup = pd.read_sql(
        "SELECT category_id, category_name FROM dim_category", conn
    )
    df_merged = df_raw.merge(cat_lookup, on="category_name")

    dim_user = df_raw[["user_id", "user_city"]].drop_duplicates(
        subset=["user_id"]
    )
    dim_user.columns = ["user_id", "city"]

    dim_product = df_merged[["product_id", "category_id"]].drop_duplicates(
        subset=["product_id"]
    )

    df_raw["date_id"] = df_raw["timestamp"].dt.strftime("%Y-%m-%d %H:00:00")
    dim_date = pd.DataFrame({"date_id": df_raw["date_id"].unique()})
    dt_series = pd.to_datetime(dim_date["date_id"])
    dim_date["year"] = dt_series.dt.year
    dim_date["month"] = dt_series.dt.month
    dim_date["day"] = dt_series.dt.day
    dim_date["hour"] = dt_series.dt.hour

    dim_user.to_sql("dim_user", conn, if_exists="append", index=False)
    dim_product.to_sql("dim_product", conn, if_exists="append", index=False)
    dim_date.to_sql("dim_date", conn, if_exists="append", index=False)

    fact_sales = df_raw[
        ["transaction_id", "user_id", "product_id", "date_id", "amount"]
    ]
    fact_sales.to_sql("fact_sales", conn, if_exists="append", index=False)
    conn.commit()


if __name__ == "__main__":
    star_db = "star_schema.db"
    snowflake_db = "snowflake_schema.db"

    
    if os.path.exists(star_db):
        os.remove(star_db)
    if os.path.exists(snowflake_db):
        os.remove(snowflake_db)

    raw_df = generate_raw_data(n_rows=1_000_000)

    conn_star = sqlite3.connect(star_db)
    conn_snowflake = sqlite3.connect(snowflake_db)

    print("Побудова схеми Зірка")
    build_star_schema(conn_star, raw_df)

    print("Побудова схеми Сніжинка")
    build_snowflake_schema(conn_snowflake, raw_df)

    conn_star.close()
    conn_snowflake.close()

    print("Бази даних успішно створені та заповнені!")