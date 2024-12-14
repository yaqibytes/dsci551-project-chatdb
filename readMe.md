# ChatDB: A Natural Language Database Query Tool

ChatDB is a web-based application that allows users to interact with SQL and NoSQL databases using natural language inputs. It bridges the gap between complex query syntax and intuitive data interaction, enabling non-technical users to work efficiently with databases.

---

## Features

- **Natural Language Query Execution**: Dynamically generate and execute SQL and MongoDB queries from natural language inputs.
- **Dataset Upload**: Easily upload CSV and JSON files to populate MySQL and MongoDB databases.
- **Database Exploration**: View database schemas and sample data through an intuitive interface.
- **Interactive Web Interface**: Real-time results and feedback through a chatbox-style UI.

---

## Directory Structure

```plaintext
chatdb/
├── static/
│   └── styles.css            # CSS file for styling the web interface
├── templates/
│   └── index.html            # HTML template for the main interface
├── uploads/
│   ├── courses.csv           # Sample CSV dataset
│   ├── students.csv          # Sample CSV dataset
│   ├── enrollments.csv       # Sample CSV dataset
│   ├── orders.json           # Sample JSON dataset
│   ├── products.json         # Sample JSON dataset
│   └── reviews.json          # Sample JSON dataset
└── app.py                    # Flask backend for handling API requests
```

---

## Setup and Installation

### Prerequisites

- Python 3.x
- MySQL Server
- MongoDB Server

### Required Python Packages

The following packages are required to run the project:

- Flask
- Flask-CORS
- MySQL Connector (`mysql-connector-python`)
- Pandas
- PyMongo
- Werkzeug

### Installation Steps

1. Clone this repository:
   ```bash
   git clone https://github.com/yaqibytes/dsci551-project-chatdb.git
   cd chatdb
   ```

2. Install required packages:
   ```bash
   pip install flask flask-cors mysql-connector-python pandas pymongo werkzeug
   ```

3. Configure databases:
   - Create a MySQL database named `chatdb`.
   - Ensure MongoDB is running locally and have database named `chatdb` .

4. Start the server:
   ```bash
   python app.py
   ```

5. Access the app:
   ```
   http://127.0.0.1:5000/
   ```

---

## Usage

1. **Upload Datasets**:
   - Navigate to the "Upload Dataset" section.
   - Upload CSV or JSON files to populate the databases.

2. **Execute Queries**:
   - Input SQL or MongoDB queries in the chatbox.
   - Click "Execute" to view results.

3. **Explore Databases**:
   - Use the "Explore" button to view schemas and sample data.

4. **Natural Language Queries**:
   - Input queries like "Show total grades by semester" or "Find students where GPA > 3.5."
   - Receive results in real time.

---

## Technology Stack

### Backend

- **Python**: Implements query processing, database interaction, and API routing.
- **Flask**: Manages APIs and server-side logic.
- **Databases**:
  - MySQL: Handles structured SQL operations.
  - MongoDB: Handles NoSQL JSON-based operations.
- **Regex**: Parses natural language inputs into meaningful queries.

### Frontend

- **HTML, CSS, JavaScript**: Builds a responsive and user-friendly interface.
- **AJAX**: Updates query results dynamically without reloading the page.

---

## Key Flask Endpoints

1. **Main Page Rendering**:
   - **Endpoint**: `/`
   - **Description**: Renders the main interface for ChatDB.

2. **File Upload**:
   - **Endpoint**: `/api/upload`
   - **Description**: Accepts CSV or JSON files and populates the databases.

3. **Explore Databases**:
   - **Endpoint**: `/api/explore`
   - **Description**: Returns schemas and sample data from SQL and MongoDB databases.

4. **Execute Queries**:
   - **Endpoint**: `/api/execute_query`
   - **Description**: Executes raw SQL or MongoDB queries and returns results.

5. **Chat Queries**:
   - **Endpoint**: `/api/chat`
   - **Description**: Handles natural language queries and converts them into database operations.

---

## Sample Datasets

The following datasets are provided for demonstration purposes:

**SQL**
- `courses.csv`
- `students.csv`
- `enrollments.csv`

**NoSQL**
- `orders.json`
- `products.json`
- `reviews.json`

---

## License

This project is part of the **DSCI551: Foundations of Data Management** coursework at the **University of Southern California**, Fall 2024. It is licensed under the MIT License.

## Acknowledgment

This project was completed as part of the curriculum for **DSCI551: Foundations of Data Management** at the **University of Southern California** in **Fall 2024**. It demonstrates concepts and practices in database management, including SQL, NoSQL, and web-based database interaction systems.

### Authors
- **Yaqi Zhang**
- **Chetan Sah**
- **Ameen Qureshi**