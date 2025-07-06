import psycopg2
import pandas as pd

import os
from dotenv import load_dotenv

load_dotenv()

# Connect to the PostgreSQL database
db_host = os.getenv('DB_HOST')
db_name = os.getenv('DB_NAME')
db_user = os.getenv('DB_USER')
db_password = os.getenv('DB_PASSWORD')

db_config = {
    "host": db_host,
    "dbname": db_name,
    "user": db_user,
    "password": db_password
}
conn = psycopg2.connect(**db_config)

# Your SQL query
query = input("query: ")

# Execute the query and load the result into a DataFrame
data_frame = pd.read_sql_query(query, conn)

# Close the database connection
conn.close()

# Save the DataFrame to an Excel file
f = input("output_name")
data_frame.to_excel(f + ".xlsx", index=False)
