import os
import sqlite3
import time
import pandas as pd


def run_performance_benchmark(
    star_db="star_schema.db", snowflake_db="snowflake_schema.db"
):
 
    if not os.path.exists(star_db) or not os.path.exists(snowflake_db):
        print(
            " Файли не знайдені!"
        )
        return

    print(" Порівняння продуктивності")

    conn_star = sqlite3.connect(star_db)
    conn_snowflake = sqlite3.connect(snowflake_db)

    #  Агрегація продажів за категоріями та місяцями
    q1_star = """
    SELECT p.category_name, d.year, d.month, SUM(f.amount) as total_sales, COUNT(*) as tx_count
    FROM fact_sales f
    JOIN dim_product p ON f.product_id = p.product_id
    JOIN dim_date d ON f.date_id = d.date_id
    GROUP BY p.category_name, d.year, d.month;
    """

    q1_snowflake = """
    SELECT c.category_name, d.year, d.month, SUM(f.amount) as total_sales, COUNT(*) as tx_count
    FROM fact_sales f
    JOIN dim_product p ON f.product_id = p.product_id
    JOIN dim_category c ON p.category_id = c.category_id
    JOIN dim_date d ON f.date_id = d.date_id
    GROUP BY c.category_name, d.year, d.month;
    """

    #  Фільтрація за конкретним містом та аналіз середнього чека
    q2_star = """
    SELECT u.city, p.category_name, AVG(f.amount) as avg_amount
    FROM fact_sales f
    JOIN dim_user u ON f.user_id = u.user_id
    JOIN dim_product p ON f.product_id = p.product_id
    WHERE u.city = 'Kyiv'
    GROUP BY u.city, p.category_name;
    """

    q2_snowflake = """
    SELECT u.city, c.category_name, AVG(f.amount) as avg_amount
    FROM fact_sales f
    JOIN dim_user u ON f.user_id = u.user_id
    JOIN dim_product p ON f.product_id = p.product_id
    JOIN dim_category c ON p.category_id = c.category_id
    WHERE u.city = 'Kyiv'
    GROUP BY u.city, c.category_name;
    """

    queries = [
        ("1. Продажі за категоріями та місяцями", q1_star, q1_snowflake),
        ("2. Середній чек по категорії для Kyiv", q2_star, q2_snowflake),
    ]

    results = []

    for name, q_star, q_snowflake in queries:
        # Виконання у зірці
        t0 = time.perf_counter()
        pd.read_sql(q_star, conn_star)
        t_star = (time.perf_counter() - t0) * 1000

        # Виконання у сніжинці
        t0 = time.perf_counter()
        pd.read_sql(q_snowflake, conn_snowflake)
        t_snowflake = (time.perf_counter() - t0) * 1000

        diff = (
            f"+{((t_snowflake - t_star) / t_star) * 100:.1f}%"
            if t_star > 0
            else "N/A"
        )

        results.append(
            {
                "Запит": name,
                "Зірка (ms)": f"{t_star:.2f}",
                "Сніжинка (ms)": f"{t_snowflake:.2f}",
                "Різниця Сніжинки": diff,
            }
        )

    conn_star.close()
    conn_snowflake.close()

  
    df_results = pd.DataFrame(results)
    print(df_results.to_string(index=False))
    print("=" * 70)


if __name__ == "__main__":
    run_performance_benchmark()