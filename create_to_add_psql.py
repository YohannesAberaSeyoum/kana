import re

path = input('input your sql path: ')

with open(path, 'r') as p:
    sql = p.read()
    tables = re.findall(r'CREATE TABLE (public.\w+)([^;]+)', sql)
    for table in tables:
        script = f'CREATE TABLE IF NOT EXISTS {table[0]} ();\n'
        columns = re.findall(r'(\S[^\n]+)', table[1])
        for column in columns:
            script += f'ALTER TABLE {table[0]} ADD COLUMN IF NOT EXISTS {column};\n'
        sql = sql.replace("CREATE TABLE " + table[0] + table[1], script)
    sql = sql.replace('CREATE SEQUENCE', 'CREATE SEQUENCE IF NOT EXISTS')
    sql = sql.replace(',;', ';')
    with open(re.sub(r'(.\w+)$', r'_altered\1', path), 'w+') as n:
        n.write(sql)
        print("The file is write into " + n.name)
        print("=====================================")
        print("You can use this script to dump file into database")
        print(f"psql -U username -d database -h host < {n.name}")