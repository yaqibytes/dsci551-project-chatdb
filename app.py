from flask import Flask, request, render_template, jsonify
import os
import re
import mysql.connector
import pandas as pd
from pymongo import MongoClient
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import json
import random
from flask_cors import CORS


app = Flask(__name__)
CORS(app) 

# Configure file upload settings
DB_TYPE=0
UPLOAD_FOLDER = 'uploads/'
ALLOWED_EXTENSIONS = {'csv', 'json'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Function to check allowed file extensions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# MySQL connection function
def get_db_connection():
    conn = mysql.connector.connect(
        host="127.0.0.1",
        port=3306,
        user="root",
        password="Dsci-551",
        database="chatdb",
        auth_plugin="mysql_native_password"
    )
    return conn


# MongoDB connection function
def get_mongo_connection():
    client = MongoClient("mongodb://localhost:27017/")
    db = client["chatdb"]
    return db


# Route to serve the main page
@app.route('/')
def index():
    return render_template('index.html')

# Route to handle file upload
# Global variable to store the name of the last uploaded table
last_uploaded_table = None

@app.route('/api/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'message': 'No file part'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'message': 'No selected file'}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        collection_name = filename.rsplit('.', 1)[0]
        if filename.endswith('.csv'):
            table_name = collection_name
            process_csv_file_and_load_to_db(filepath, table_name)
        elif filename.endswith('.json'):
            process_json_file_and_load_to_mongo(filepath, collection_name)
         
        return jsonify({'message': 'File successfully uploaded', 'filename': filename}), 200
    else:
        return jsonify({'message': 'Invalid file type'}), 400


def create_table_from_csv(conn, df, table_name):
    cursor = conn.cursor()
    cursor.execute(f"DROP TABLE IF EXISTS {table_name};")
    conn.commit()

    column_definitions = []
    for col in df.columns:
        col_type = df[col].dtype
        if col_type == 'int64':
            sql_type = 'INT'
        elif col_type == 'float64':
            sql_type = 'FLOAT'
        elif col_type == 'bool':
            sql_type = 'BOOLEAN'
        elif pd.api.types.is_datetime64_any_dtype(df[col]):
            sql_type = 'DATETIME'
        else:
            sql_type = 'VARCHAR(255)'
        column_definitions.append(f"{col} {sql_type}")

    columns = ", ".join(column_definitions)
    cursor.execute(f"CREATE TABLE IF NOT EXISTS {table_name} ({columns});")
    conn.commit()

def process_csv_file_and_load_to_db(filepath, table_name):
    df = pd.read_csv(filepath)
    conn = get_db_connection()
    create_table_from_csv(conn, df, table_name)

    columns = ", ".join(df.columns)
    placeholders = ", ".join(["%s"] * len(df.columns))
    insert_query = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"

    cursor = conn.cursor()
    for index, row in df.iterrows():
        try:
            values = [None if pd.isna(value) else value for value in row]
            cursor.execute(insert_query, tuple(values))
        except mysql.connector.Error as err:
            print(f"Error inserting row {index}: {err}")
            conn.rollback()
    conn.commit()
    conn.close()


def preprocess_json_data(data):
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, dict):
                if '$oid' in value:
                    data[key] = value['$oid']
                elif '$date' in value:
                    try:
                        data[key] = datetime.fromisoformat(value['$date'].replace("Z", "+00:00"))
                    except ValueError:
                        data[key] = value['$date']
                else:
                    preprocess_json_data(value)
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    preprocess_json_data(item)
            elif isinstance(value, str):
                try:
                    parsed_date = datetime.fromisoformat(value)
                    data[key] = parsed_date
                except ValueError:
                    pass
    elif isinstance(data, list):
        for item in data:
            preprocess_json_data(item)

def process_json_file_and_load_to_mongo(filepath, collection_name):
    db = get_mongo_connection()
    collection = db[collection_name]
    if collection_name in db.list_collection_names():
        collection.drop()

    with open(filepath, 'r') as json_file:
        data = json.load(json_file)
    preprocess_json_data(data)
    if isinstance(data, list):
        collection.insert_many(data)
    else:
        collection.insert_one(data)
 
# Route to explore MySQL databases and show tables
@app.route('/api/explore', methods=['POST'])
def explore():
    db_type = request.json.get('db_type', '').lower()

    if db_type == 'mysql':
        try:
            connection = get_db_connection()  # Use your existing MySQL connection function
            cursor = connection.cursor()
            cursor.execute("SHOW TABLES")
            tables = cursor.fetchall()

            table_details = {}
            for table in tables:
                table_name = table[0]
                cursor.execute(f"DESCRIBE {table_name}")
                attributes = cursor.fetchall()
                # Fetch sample data
                cursor.execute(f"SELECT * FROM {table_name} LIMIT 5")
                sample_data = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]
                
                # Format the sample data
                sample_data_formatted = []
                for row in sample_data:
                    formatted_row = {}
                    for col, val in zip(columns, row):
                        # Convert timedelta to string
                        if isinstance(val, timedelta):
                            formatted_row[col] = str(val)
                        else:
                            formatted_row[col] = val
                    sample_data_formatted.append(formatted_row)

                table_details[table_name] = {
                    'attributes': attributes,
                    'sample_data': sample_data_formatted
                }

            cursor.close()
            connection.close()

            return jsonify({"db_type": "mysql", "tables": table_details})

        except Exception as e:
            return jsonify({"error": str(e)})


    elif db_type == 'mongodb':
        try:
            db = get_mongo_connection()
            collection_names = db.list_collection_names()
            collection_details = {}

            for collection_name in collection_names:
                collection = db[collection_name]
                attributes = list(collection.find_one().keys()) if collection.find_one() else []
                sample_data = list(collection.find().limit(5))

                collection_details[collection_name] = {
                    'attributes': attributes,
                    'sample_data': sample_data
                }

            return jsonify({"db_type": "mongodb", "collections": collection_details})

        except Exception as e:
            return jsonify({"error": str(e)})

    else:
        return jsonify({"error": "Invalid database type specified."})



# Route to handle receiving and executing MySQL queries
@app.route('/api/execute_query', methods=['POST'])
def execute_query():
    user_query = request.json.get('query')
    db_type = request.json.get('db_type', 'mysql').lower()

    if not user_query:
        return jsonify({'error': 'No query provided'}), 400
    
    if db_type == 'mysql':
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            # Run the query only when this endpoint is explicitly called
            cursor.execute(user_query)
            rows = cursor.fetchall()
            conn.commit()

            headers = [desc[0] for desc in cursor.description] if cursor.description else []
            result = []
            for row in rows:
                formatted_row = [str(item) if isinstance(item, timedelta) else item for item in row]
                result.append(formatted_row)

            return jsonify({'headers': headers, 'result': result}), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 400
        finally:
            conn.close()
    
    elif db_type == 'mongodb':
        # MongoDB Query Handling
        db = get_mongo_connection()
        try:
            user_query = json.loads(user_query)  # Parse the input query
            collection_name = user_query.get('collection')
            query = user_query.get('query', {})
            projection = user_query.get('projection')  # Optional projection
            sort = user_query.get('sort')  # Optional sort
            limit = user_query.get('limit')  # Optional limit
            skip = user_query.get('skip')  # Optional skip
            aggregation = user_query.get('aggregation')  # Optional aggregation pipeline
            lookup = user_query.get('lookup')  # Optional lookup
            unwind = user_query.get('unwind')  # Optional unwind
            group = user_query.get('group')  # Optional group

            collection = db[collection_name]

            pipeline = aggregation if aggregation else []

            if lookup:
                pipeline.append({
                    '$lookup': {
                        'from': lookup.get('from'),
                        'localField': lookup.get('localField'),
                        'foreignField': lookup.get('foreignField'),
                        'as': lookup.get('as')
                    }
                })
            if unwind:
                pipeline.append({'$unwind': unwind})
            if group:
                pipeline.append({'$group': group})
            if query:
                pipeline.append({'$match': query})
            if projection:
                pipeline.append({'$project': projection})
            if sort:
                pipeline.append({'$sort': sort})
            if skip:
                pipeline.append({'$skip': skip})
            if limit:
                pipeline.append({'$limit': limit})

            documents = list(collection.aggregate(pipeline))

            headers = list(documents[0].keys()) if documents else []
            result = [list(doc.values()) for doc in documents]

            return jsonify({'headers': headers, 'result': result}), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 400

    else:
        return jsonify({'error': 'Invalid database type specified'}), 400



# SQL Database schema and attributes
SQL_DATABASES = {
    "chatDB": {
        "courses": ["CourseID", "CourseName", "InstructorID", "InstructorName", "CreditHours"],
        "enrollments": ["EnrollmentID", "StudentID", "CourseID", "Semester", "Grade"],
        "students": ["StudentID", "FirstName", "LastName", "Email", "Major", "AdvisorID", "AdvisorName"]
    }
}

# SQL Quantitative and Qualitative Attributes
SQL_QUANTITATIVE_ATTRIBUTES = {
    "courses": ["CreditHours"],
    "enrollments": ["Grade"],
    "students": []
}

SQL_QUALITATIVE_ATTRIBUTES = {
    "courses": ["CourseID", "CourseName", "InstructorID", "InstructorName"],
    "enrollments": ["StudentID", "CourseID", "Semester"],
    "students": ["StudentID", "FirstName", "LastName", "Email", "Major", "AdvisorID", "AdvisorName"]
}

# SQL Query patterns and templates
SQL_QUERY_PATTERNS = {
    "group by": "total <A> by <B>",
    "average": "average <A> by <B>",
    "count group by": "count <B> by <A>",
    "greater than": "find <A> greater than a threshold",
    "less than": "find <A> less than a threshold",
    "between": "find <A> between two values",
    "order by": "list all <B> sorted by <A>",
    "top n order by": "top <N> <B> by <A>",
    "having": "having <A> greater/less than a threshold",
    "join": "join <T1> and <T2> on <T1>.<C1> = <T2>.<C2>",
    "where equals": "find <B> where <A> is equal to <value>",
    "where contains": "find <B> where <A> contains <value>"
}

# SQL Natural Language Parsing Regex Patterns
SQL_NATURAL_LANGUAGE_PATTERNS = [
    (re.compile(r"total (\w+) by (\w+)"), "group by"),
    (re.compile(r"average (\w+) by (\w+)"), "average"),
    (re.compile(r"count (\w+) by (\w+)"), "count group by"),
    (re.compile(r"find (\w+) greater than (\d+)"), "greater than"),
    (re.compile(r"find (\w+) less than (\d+)"), "less than"),
    (re.compile(r"find (\w+) between (\d+) and (\d+)"), "between"),
    (re.compile(r"list all (\w+) sorted by (\w+) in (ascending|descending) order"), "order by"),
    (re.compile(r"top (\d+) (\w+) by (\w+)"), "top n order by"),
    (re.compile(r"find (\w+) having (\w+) greater than (\d+)"), "having"),
    (re.compile(r"join (\w+) and (\w+) on (\w+)\.(\w+) = (\w+)\.(\w+)"), "join"),
    (re.compile(r"find (\w+) where (\w+) is (\w+)"), "where equals"),
    (re.compile(r"find (\w+) where (\w+) contains '(.+?)'"), "where contains"),
]

# Explore SQL Databases
def SQL_explore_databases():
    response = "Available Databases and Tables:\n"
    for db_name, tables in SQL_DATABASES.items():
        response += f"- {db_name}:\n"
        for table, fields in tables.items():
            fields_formatted = ", ".join(fields)  # Concatenate fields with commas
            response += f"  - Table: {table}\n"
            response += f"    Fields: {fields_formatted}\n"  # Add fields in one line
    return response



# Generate SQL query based on a construct
def SQL_generate_query_with_construct(table, construct):
    if table not in SQL_DATABASES["chatDB"]:
        return "Invalid table specified."

    quantitative_attrs = SQL_QUANTITATIVE_ATTRIBUTES.get(table, [])
    qualitative_attrs = SQL_QUALITATIVE_ATTRIBUTES.get(table, [])

    if not quantitative_attrs or not qualitative_attrs:
        return "Insufficient attributes to generate queries."

    A = random.choice(quantitative_attrs)
    B = random.choice(qualitative_attrs)

    if construct == "group by":
        return f"SELECT {B}, SUM({A}) AS total_{A} FROM {table} GROUP BY {B};"
    elif construct == "average":
        return f"SELECT {B}, AVG({A}) AS average_{A} FROM {table} GROUP BY {B};"
    elif construct == "count group by":
        return f"SELECT {B}, COUNT({A}) AS count_{A} FROM {table} GROUP BY {B};"
    elif construct == "greater than":
        return f"SELECT * FROM {table} WHERE {A} > 1;"
    elif construct == "less than":
        return f"SELECT * FROM {table} WHERE {A} < 1;"
    elif construct == "between":
        return f"SELECT * FROM {table} WHERE {A} BETWEEN 50 AND 60;"
    elif construct == "order by":
        return f"SELECT * FROM {table} ORDER BY {A} ASC;"
    elif construct == "top n order by":
        return f"SELECT * FROM {table} ORDER BY {A} DESC LIMIT 10;"
    elif construct == "having":
        return f"SELECT {B}, SUM({A}) AS total_{A} FROM {table} GROUP BY {B} HAVING SUM({A}) > 1;"
    elif construct == "join":
        return f"SELECT * FROM {table} T1 INNER JOIN {random.choice(list(SQL_DATABASES['chatDB'].keys()))} T2 ON T1.{B} = T2.{B};"
    elif construct == "where equals":
        return f"SELECT * FROM {table} WHERE {B} = 'value';"
    elif construct == "where contains":
        return f"SELECT * FROM {table} WHERE {B} LIKE '%value%';"
    else:
        return "Construct not recognized."

# Generate predefined SQL sample queries
def SQL_generate_sample_queries(table):
    queries_map = {
        "courses": [
            "SELECT CourseID, CourseName FROM courses;",
            "SELECT InstructorID, COUNT(*) AS course_count FROM courses GROUP BY InstructorID;",
            "SELECT AVG(CreditHours) AS average_credits FROM courses;",
            "SELECT CourseID, CreditHours FROM courses WHERE CreditHours > 3;",
            "SELECT * FROM courses ORDER BY CreditHours DESC;",
            "SELECT DISTINCT InstructorID FROM courses;",
            "SELECT CourseName FROM courses WHERE CreditHours = 3;"
        ],
        "enrollments": [
            "SELECT StudentID, CourseID FROM enrollments;",
            "SELECT Semester, COUNT(*) AS enrollment_count FROM enrollments GROUP BY Semester;",
            "SELECT AVG(Grade) AS average_grade FROM enrollments;",
            "SELECT * FROM enrollments WHERE Grade > 85;",
            "SELECT CourseID, COUNT(*) AS student_count FROM enrollments GROUP BY CourseID;",
            "SELECT DISTINCT Semester FROM enrollments;",
            "SELECT StudentID FROM enrollments WHERE CourseID = 'CS101';"
        ],
        "students": [
            "SELECT StudentID, FirstName, LastName FROM students;",
            "SELECT Major, COUNT(*) AS major_count FROM students GROUP BY Major;",
            "SELECT * FROM students WHERE AdvisorID IS NOT NULL;",
            "SELECT Email FROM students WHERE Major LIKE '%Computer Science%';",
            "SELECT DISTINCT Major FROM students;",
            "SELECT FirstName, LastName FROM students ORDER BY LastName ASC;",
            "SELECT StudentID FROM students WHERE Major = 'Computer Science';"
        ]
    }

    if table not in queries_map:
        return ["Invalid table specified."]
    return random.sample(queries_map[table], 3)

# Generate SQL query from natural language
def SQL_generate_query_from_natural_language(message, table):
    for pattern, construct in SQL_NATURAL_LANGUAGE_PATTERNS:
        match = pattern.search(message)
        if match:
            return SQL_generate_query_with_construct(table, construct)
    return "Could not interpret the request."

def determine_SQL_response(message):
    message = message.lower()

    # Handle explore request
    if "explore" in message:
        return SQL_explore_databases()

    # Handle sample queries request
    if "sample" in message:
        for table in SQL_DATABASES["chatDB"].keys():
            if table in message:
                return "\n".join(SQL_generate_sample_queries(table))
        return "Please specify a valid table: 'courses', 'enrollments', 'sales', or 'students'."

    # Handle construct keywords and specific tables
    for construct in SQL_QUERY_PATTERNS.keys():
        if construct in message:
            for table in SQL_DATABASES["chatDB"].keys():
                if table in message:
                    return SQL_generate_query_with_construct(table, construct)

    # Handle natural language query
    for table in SQL_DATABASES["chatDB"].keys():
        if table in message:
            return SQL_generate_query_from_natural_language(message, table)

    return "Error: Could not interpret the request."

DATABASES = {
    "chatDB": {
        "products": {
            "fields": ["_id", "name", "description", "category", "price", "stock", "brand", "createdAt", "ratings"]
        },
        "orders": {
            "fields": ["_id", "userId", "items", "totalAmount", "orderDate", "status", "shippingAddress", "itemCount"]
        },
        "reviews": {
            "fields": ["_id", "userId", "productId", "rating", "review", "createdAt"]
        }
    }
}

QUANTITATIVE_ATTRIBUTES = {
    "products": ["price", "stock", "ratings.rating"],
    "orders": ["totalAmount", "itemCount"],
    "reviews": ["rating"]
}

QUALITATIVE_ATTRIBUTES = {
    "products": ["brand", "category", "name"],
    "orders": ["status", "userId", "shippingAddress.city", "shippingAddress.country", "orderDate"],
    "reviews": ["userId", "productId", "review", "createdAt"]
}

CONSTRUCT_KEYWORDS = {
    "group by": "total <A> by <B>",
    "average": "average <A> by <B>",
    "count": "count of <B>",
    "greater than": "find <A> greater than a threshold",
    "less than": "find <A> less than a threshold",
    "sorted by": "list all <B> sorted by <A>",
    "aggregation": "aggregation construct",
    "having": "having construct",
    "unwind": "unwind <B> to flatten arrays",
    "lookup": "join <B> with <C> on <D>",
    "projection": "project only <A> and <B>"
}

def explore_databases():
    response = "Available Databases and Collections:\n"
    for db_name, collections in DATABASES.items():
        response += f"- {db_name}:\n"
        for collection, details in collections.items():
            fields = ", ".join(details["fields"])
            response += f"  - Collection: {collection}\n"
            response += f"    Fields: {fields}\n"
    return response.strip()

QUERY_PATTERNS = [
    (re.compile(r"(find|show|list)\s+total\s+(\w+)\s+by\s+(\w+)\s+in\s+(\w+)"), "total <A> by <B>"),
    (re.compile(r"(find|show|list)\s+average\s+(\w+)\s+by\s+(\w+)\s+in\s+(\w+)"), "average <A> by <B>"),
    (re.compile(r"(find|show|list)\s+count\s+of\s+(\w+)\s+in\s+(\w+)"), "count of <B>"),
    (re.compile(r"(find|list)\s+(\w+)\s+greater\s+than\s+(\d+)\s+in\s+(\w+)"), "find <A> greater than a threshold"),
    (re.compile(r"(find|list)\s+(\w+)\s+less\s+than\s+(\d+)\s+in\s+(\w+)"), "find <A> less than a threshold"),
    (re.compile(r"(list|show)\s+all\s+(\w+)\s+sorted\s+by\s+(\w+)\s+in\s+(\w+)"), "list all <B> sorted by <A>"),
    (re.compile(r"unwind\s+(\w+)\s+in\s+(\w+)"), "unwind <B> to flatten arrays"),
    (re.compile(r"join\s+(\w+)\s+with\s+(\w+)\s+on\s+(\w+)"), "join <B> with <C> on <D>"),
    (re.compile(r"project\s+only\s+(\w+)\s+and\s+(\w+)\s+in\s+(\w+)"), "projection")
]

def generate_mongo_query(template, collection):
    quantitative_attrs = QUANTITATIVE_ATTRIBUTES.get(collection, [])
    qualitative_attrs = QUALITATIVE_ATTRIBUTES.get(collection, [])

    if not quantitative_attrs or not qualitative_attrs:
        return "Error: Invalid dataset or attributes."

    quantitative_attr = random.choice(quantitative_attrs)
    qualitative_attr = random.choice(qualitative_attrs)

    if template == "total <A> by <B>":
        return f'''
db.{collection}.aggregate([
    {{
        "$group": {{
            "_id": "${qualitative_attr}",
            "total_{quantitative_attr}": {{
                "$sum": "${quantitative_attr}"
            }}
        }}
    }}
])
'''
    elif template == "average <A> by <B>":
        return f'''
db.{collection}.aggregate([
    {{
        "$group": {{
            "_id": "${qualitative_attr}",
            "average_{quantitative_attr}": {{
                "$avg": "${quantitative_attr}"
            }}
        }}
    }}
])
'''
    elif template == "count of <B>":
        return f'''
db.{collection}.aggregate([
    {{
        "$group": {{
            "_id": "${qualitative_attr}",
            "count": {{
                "$sum": 1
            }}
        }}
    }}
])
'''
    elif template == "find <A> greater than a threshold":
        return f'''
db.{collection}.find({{
    "{quantitative_attr}": {{
        "$gt": 1
    }}
}})
'''
    elif template == "list all <B> sorted by <A>":
        return f'''
db.{collection}.find().sort({{
    "{quantitative_attr}": 1
}})
'''
    elif template == "unwind <B> to flatten arrays":
        return f'''
db.{collection}.aggregate([
    {{
        "$unwind": "${qualitative_attr}"
    }}
])
'''
    elif template == "join <B> with <C> on <D>":
        foreign_collection = random.choice(list(DATABASES["chatDB"].keys()))
        foreign_field = random.choice(DATABASES["chatDB"][foreign_collection]["fields"])
        return f'''
db.{collection}.aggregate([
    {{
        "$lookup": {{
            "from": "{foreign_collection}",
            "localField": "{qualitative_attr}",
            "foreignField": "{foreign_field}",
            "as": "joined_data"
        }}
    }}
])
'''
    elif template == "projection":
        second_field = random.choice(qualitative_attrs)
        return f'''
db.{collection}.find({{ }}, {{
    "{qualitative_attr}": 1,
    "{second_field}": 1
}})
'''
    else:
        return "Error: Invalid query template."

def generate_sample_queries(collection):
    queries_map = {
        "products": [
            '''db.products.aggregate([{"$group": {"_id": "$brand", "total_stock": {"$sum": "$stock"}}}])''',
            '''db.products.find({"price": {"$gt": 100}}).sort({"price": -1})''',
            '''db.products.distinct("category")''',
            '''db.products.find({"category": "electronics"})''',
            '''db.products.find().limit(5)''',
            '''db.products.aggregate([{"$match": {"brand": "BrandX"}}])'''
        ],
        "orders": [
            '''db.orders.aggregate([{"$group": {"_id": "$status", "total_amount": {"$sum": "$totalAmount"}}}])''',
            '''db.orders.find({"totalAmount": {"$gte": 500}}).sort({"totalAmount": -1})''',
            '''db.orders.distinct("status")''',
            '''db.orders.find({"status": "pending"})''',
            '''db.orders.aggregate([{"$unwind": "$items"}])''',
            '''db.orders.find().skip(10).limit(5)'''
        ],
        "reviews": [
            '''db.reviews.aggregate([{"$group": {"_id": "$productId", "average_rating": {"$avg": "$rating"}}}])''',
            '''db.reviews.find({"rating": {"$gt": 4}})''',
            '''db.reviews.distinct("productId")''',
            '''db.reviews.find({"review": {"$regex": "good", "$options": "i"}})''',
            '''db.reviews.find({"userId": "user123"})''',
            '''db.reviews.aggregate([{"$lookup": {"from": "products", "localField": "productId", "foreignField": "_id", "as": "productDetails"}}])'''
        ]
    }

    if collection not in queries_map:
        return ["Invalid collection specified."]
    return random.sample(queries_map[collection], 3)

def determine_response(message):
    message = message.lower()

    if "explore" in message:
        return explore_databases()

    if "sample" in message:
        for collection in DATABASES["chatDB"].keys():
            if collection in message:
                return "\n".join(generate_sample_queries(collection))
        return "Please specify a valid collection: 'products', 'orders', or 'reviews'."

    for construct in CONSTRUCT_KEYWORDS.keys():
        if construct in message:
            for collection in DATABASES["chatDB"].keys():
                if collection in message:
                    return generate_mongo_query(CONSTRUCT_KEYWORDS[construct], collection)

    for pattern, template in QUERY_PATTERNS:
        match = pattern.search(message)
        if match:
            collection = match.groups()[-1]
            if collection in DATABASES["chatDB"]:
                return generate_mongo_query(template, collection)

    return "Error: Could not interpret the Query"



@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        data = request.get_json()
        if not data or 'message' not in data:
            return jsonify({'response': 'Error: No input provided.'}), 400

        message = data['message']
        first_word = message.split(' ')[0].lower()

        if first_word == "sql":
            try:
                response = determine_SQL_response(message[len("sql "):])
                return jsonify({'response': response}), 200
            except Exception as e:
                return jsonify({'response': f"Failed to process SQL query: {str(e)}"}), 500

        elif first_word == "nosql":
            try:
                response = determine_response(message[len("nosql "):])
                return jsonify({'response': response}), 200
            except Exception as e:
                return jsonify({'response': f"Failed to process NoSQL query: {str(e)}"}), 500

        else:
            return jsonify({'response': 'Error: Invalid database type specified. Use SQL or NoSQL.'}), 400

    except Exception as e:
        return jsonify({'response': f"Internal server error: {str(e)}"}), 500


    
if __name__ == '__main__':
    app.run()
