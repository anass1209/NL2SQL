# sql_pipeline.py - VERSION RENFORCÉE
import os
import traceback
import re
from typing import Dict, Any, Optional, List, Tuple
import json

import psycopg2
from psycopg2 import sql

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from langchain_core.messages import SystemMessage, HumanMessage

# --- Lazy Initialization for LLM ---
def get_google_llm(temperature=0.1) -> Optional[ChatGoogleGenerativeAI]:
    """Lazily initializes the Google Generative AI model."""
    google_key = os.environ.get("GOOGLE_API_KEY")
    if google_key:
        try:
            return ChatGoogleGenerativeAI(model="gemini-1.5-pro-latest", temperature=temperature, top_p=0.8)
        except Exception as e:
            print(f"Error initializing Google LLM (key might be invalid): {e}")
            traceback.print_exc()
            return None
    else:
        print("ERROR: Google API Key not found in environment for LLM.")
        return None

# --- Database Interaction ---
def get_db_connection(db_config: Dict[str, str]) -> Optional[psycopg2.extensions.connection]:
    """Establishes a connection to the PostgreSQL database."""
    try:
        conn = psycopg2.connect(
            host=db_config.get("db_host"),
            port=db_config.get("db_port"),
            dbname=db_config.get("db_name"),
            user=db_config.get("db_user"),
            password=db_config.get("db_password")
        )
        print("Database connection successful.")
        return conn
    except psycopg2.Error as e:
        print(f"Error connecting to database: {e}")
        traceback.print_exc()
        return None

def get_actual_schema(conn: psycopg2.extensions.connection) -> Dict[str, List[str]]:
    """
    Queries the database to get the actual schema structure.
    Returns a dictionary with table names as keys and column lists as values.
    """
    schema = {}
    try:
        with conn.cursor() as cur:
            # Get all tables in the public schema
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                AND table_type = 'BASE TABLE'
            """)
            tables = cur.fetchall()
            
            # For each table, get the column names and types
            for table in tables:
                table_name = table[0]
                cur.execute("""
                    SELECT column_name, data_type
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = %s
                    ORDER BY ordinal_position
                """, (table_name,))
                columns = cur.fetchall()
                
                schema[table_name] = [f"{col[0]} {col[1]}" for col in columns]
        
        return schema
    except Exception as e:
        print(f"Error getting actual schema: {e}")
        return {}

def schema_to_formatted_string(schema: Dict[str, List[str]]) -> str:
    """
    Converts a schema dictionary to a formatted string for the LLM prompt.
    """
    schema_str = "Database Schema:\n"
    for table, columns in schema.items():
        schema_str += f"Table {table}:\n"
        schema_str += f"  Columns: {', '.join(columns)}\n"
    
    return schema_str

def get_sample_data(conn: psycopg2.extensions.connection, max_rows=3) -> Dict[str, List[Dict]]:
    """
    Gets sample data from each table to help with query generation.
    """
    sample_data = {}
    try:
        with conn.cursor() as cur:
            # Get all tables
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                AND table_type = 'BASE TABLE'
            """)
            tables = [t[0] for t in cur.fetchall()]
            
            # For each table, get sample data
            for table in tables:
                try:
                    cur.execute(f"SELECT * FROM {table} LIMIT {max_rows}")
                    if cur.description:
                        columns = [desc[0] for desc in cur.description]
                        rows = cur.fetchall()
                        
                        # Convert to list of dictionaries for easier JSON serialization
                        table_data = []
                        for row in rows:
                            row_dict = {}
                            for i, col in enumerate(columns):
                                # Handle special PostgreSQL types that don't serialize well
                                if hasattr(row[i], 'isoformat'):  # For dates and timestamps
                                    row_dict[col] = row[i].isoformat()
                                else:
                                    row_dict[col] = row[i]
                            table_data.append(row_dict)
                        
                        sample_data[table] = table_data
                except Exception as table_e:
                    print(f"Error getting sample data for table {table}: {table_e}")
                    continue
        
        return sample_data
    except Exception as e:
        print(f"Error getting sample data: {e}")
        return {}

def execute_sql(conn: psycopg2.extensions.connection, sql_query: str) -> Tuple[Optional[List[Tuple]], Optional[List[str]], Optional[str]]:
    """
    Executes a SQL query (expects SELECT) and fetches results.
    """
    results = None
    columns = None
    error_message = None
    print(f"Executing SQL: {sql_query}")

    # Basic safety check: Only allow SELECT statements for now
    if not sql_query.strip().upper().startswith("SELECT"):
        error_message = "Error: Only SELECT queries are allowed for safety."
        print(error_message)
        return results, columns, error_message

    try:
        with conn.cursor() as cur:
            cur.execute(sql_query)
            # Check if the cursor description is available (means it was a query that returns rows)
            if cur.description:
                columns = [desc[0] for desc in cur.description]
                results = cur.fetchall()
                print(f"Query executed successfully. Fetched {len(results)} rows.")
            else:
                print("Query executed, but no rows returned or structure indeterminable.")
                results = []
                columns = []

    except psycopg2.Error as e:
        error_message = f"Database Execution Error: {e}"
        print(error_message)
        traceback.print_exc()
        conn.rollback()
    except Exception as e:
        error_message = f"Unexpected Error during SQL Execution: {e}"
        print(error_message)
        traceback.print_exc()
        conn.rollback() # Rollback on any exception

    return results, columns, error_message

# --- Pre-Query Analysis ---
def analyze_user_intent(user_query: str, llm: ChatGoogleGenerativeAI) -> Dict[str, Any]:
    """
    Analyzes the user's query intent before generating SQL.
    This helps identify key entities, filters, and actions.
    """
    if not llm:
        return {"error": "LLM not available"}
    
    intent_system_message = """You are an expert in understanding database query intentions.
    Analyze the user's natural language query and extract key information.
    Your output should be a JSON object with these fields:
    - correction: A corrected version of the query with typos fixed
    - tables: Array of table names likely needed (e.g., "customers", "orders")
    - filters: Object with column names and values to filter by (e.g., {"city": "Casablanca"})
    - actions: Simple description of the query intent (e.g., "list", "count", "find", "show")
    - language: Either "english" or "french"

    For example:
    Query: "show me all cutomers from casablanca"
    Response: {
    "correction": "show me all customers from casablanca",
    "tables": ["customers"],
    "filters": {"city": "Casablanca"},
    "actions": "list",
    "language": "english" 
    }"""
        
    try:
        analysis_llm = get_google_llm(temperature=0.3)
        if not analysis_llm:
            return {"error": "Could not initialize analysis LLM"}
            
        # Use a direct approach instead of LCEL
        messages = [
            SystemMessage(content=intent_system_message),
            HumanMessage(content=f"Analyze this query: {user_query}")
        ]
        
        # Invoke the LLM directly with messages
        result = analysis_llm.invoke(messages)
        
        # Extract JSON object - the LLM might wrap it in markdown code blocks
        json_match = re.search(r'\{[\s\S]*\}', result.content)
        if json_match:
            json_str = json_match.group(0)
            return json.loads(json_str)
        else:
            # If no JSON format detected, return error
            print(f"Failed to parse intent analysis result: {result.content}")
            return {
                "error": "Failed to parse intent analysis",
                "raw_result": result.content
            }
    except Exception as e:
        print(f"Error in intent analysis: {e}")
        traceback.print_exc()
        return {"error": f"Intent analysis failed: {str(e)}"}

# --- Enhanced SQL Generation ---
def generate_sql_query(user_query: str, intent_analysis: Dict[str, Any], 
                      schema_str: str, sample_data: Dict[str, List[Dict]], 
                      llm: ChatGoogleGenerativeAI) -> Tuple[Optional[str], Optional[str]]:
    """
    Generates SQL query from natural language using the LLM,
    enhanced with intent analysis and sample data.
    """
    if not llm:
        return None, "LLM is not available (check API Key?)."
    
    # Prepare sample data string for the prompt
    sample_data_str = "Sample data from relevant tables:\n"
    for table in intent_analysis.get("tables", []):
        if table in sample_data and sample_data[table]:
            sample_data_str += f"\nTable {table} (first {len(sample_data[table])} rows):\n"
            # Format first 2 rows as a table
            if sample_data[table]:
                # Get column names from first row
                columns = list(sample_data[table][0].keys())
                sample_data_str += "| " + " | ".join(columns) + " |\n"
                sample_data_str += "| " + " | ".join(["---" for _ in columns]) + " |\n"
                
                # Add data rows
                for row in sample_data[table]:
                    sample_data_str += "| " + " | ".join([str(row.get(col, "")) for col in columns]) + " |\n"
    
    # Add user intent information
    intent_str = "User query intent analysis:\n"
    intent_str += f"- Corrected query: {intent_analysis.get('correction', user_query)}\n"
    intent_str += f"- Likely tables needed: {', '.join(intent_analysis.get('tables', []))}\n"
    intent_str += f"- Requested filters: {intent_analysis.get('filters', {})}\n"
    intent_str += f"- Query action: {intent_analysis.get('actions', 'unknown')}\n"
    intent_str += f"- Query language: {intent_analysis.get('language', 'unknown')}\n"
    
    # Create examples specific to the intent
    examples = generate_examples_for_intent(intent_analysis, sample_data)
    
    prompt_template = ChatPromptTemplate.from_messages([
        SystemMessage(
        content=f"""You are an expert PostgreSQL SQL generator.
        Your task is to generate a valid SQL query based on the user's natural language request.

        {intent_str}

        {schema_str}

        {sample_data_str}

        CRITICAL RULES:
        1. Generate ONLY a valid PostgreSQL SQL query that matches the user's intent.
        2. The query MUST use only tables and columns that exist in the schema.
        3. Filters should match the user's request exactly (e.g., city='Casablanca' if asked for Casablanca).
        4. Use the correct case for table and column names as shown in the schema.
        5. Include appropriate JOINs only if needed to fulfill the query.
        6. Return only the SQL query string with no additional text or explanation.
        7. End the query with a semicolon.
        8. If a filter value is mentioned in the query, make sure to include it with proper SQL syntax.

        Examples:
        {examples}
        """""
        ),
        HumanMessage(content="Generate a SQL query for: {user_query}")
    ])
    
    # Using LCEL for the chain
    sql_generation_chain = prompt_template | llm | StrOutputParser()

    generated_sql = None
    error_message = None
    try:
        print("Generating SQL query...")
        generated_sql_raw = sql_generation_chain.invoke({"user_query": user_query})
        print(f"Raw LLM Response: '{generated_sql_raw}'")

        # Clean up potential markdown fences or extra text
        sql_match = re.search(r'(SELECT\s+[\s\S]+;)', generated_sql_raw, re.IGNORECASE | re.DOTALL)
        if sql_match:
            generated_sql = sql_match.group(1).strip()
        else:
            # If no semicolon, take the whole response
            if "SELECT" in generated_sql_raw.upper():
                generated_sql = generated_sql_raw.strip()
                if not generated_sql.endswith(';'):
                    generated_sql += ';'
            else:
                error_message = "Generated response doesn't contain a valid SQL query."
                print(error_message)

    except Exception as e:
        error_message = f"LLM Invocation Error: {e}"
        print(error_message)
        traceback.print_exc()
        if "API key not valid" in str(e) or "API_KEY_INVALID" in str(e):
            error_message = "API_KEY_INVALID: The Google API key provided is invalid or has expired."

    return generated_sql, error_message

def generate_examples_for_intent(intent_analysis: Dict[str, Any], 
                                sample_data: Dict[str, List[Dict]]) -> str:
    """
    Generates SQL examples specific to the detected intent.
    """
    examples = ""
    action = intent_analysis.get("actions", "").lower()
    tables = intent_analysis.get("tables", [])
    filters = intent_analysis.get("filters", {})
    language = intent_analysis.get("language", "english").lower()
    
    # Generate examples based on intent
    if "customers" in tables:
        if "city" in filters:
            city_value = filters["city"]
            if language == "french":
                examples += f"""
                Requête: Montre-moi tous les clients de {city_value}
                SQL: SELECT * FROM customers WHERE city = '{city_value}';

                Requête: Combien de clients vivent à {city_value}?
                SQL: SELECT COUNT(*) FROM customers WHERE city = '{city_value}';
                """
            else:
                examples += f"""
                Query: Show me all customers from {city_value}
                SQL: SELECT * FROM customers WHERE city = '{city_value}';

                Query: Count how many customers are from {city_value}
                SQL: SELECT COUNT(*) FROM customers WHERE city = '{city_value}';
                """
                    
    # more examples for orders and products
    if "orders" in tables:
        if language == "french":
            examples += """
                Requête: Montrez-moi toutes les commandes
                SQL: SELECT * FROM orders;

                Requête: Combien de commandes avons-nous au total?
                SQL: SELECT COUNT(*) FROM orders;
                """
        else:
            examples += """
                Query: Show me all orders
                SQL: SELECT * FROM orders;

                Query: How many orders do we have in total?
                SQL: SELECT COUNT(*) FROM orders;
                """
    
    # If customers and orders are both relevant, add examples with joins
    if "customers" in tables and "orders" in tables:
        if language == "french":
            examples += """
                Requête: Montrez-moi les clients et leurs commandes
                SQL: SELECT c.*, o.* FROM customers c JOIN orders o ON c.customer_id = o.customer_id;
                """
        else:
            examples += """
                Query: Show me customers and their orders
                SQL: SELECT c.*, o.* FROM customers c JOIN orders o ON c.customer_id = o.customer_id;
                """
    
    if not examples:
        if language == "french":
            examples += """
            Requête: Montrez-moi tous les clients
            SQL: SELECT * FROM customers;

            Requête: Listez tous les produits
            SQL: SELECT * FROM products;
            """
        else:
            examples += """
            Query: Show me all customers
            SQL: SELECT * FROM customers;

            Query: List all products
            SQL: SELECT * FROM products;
            """
    
    return examples

# --- Query Validation With Feedback ---
def validate_sql_query(generated_sql: str, intent_analysis: Dict[str, Any], 
                      schema: Dict[str, List[str]], conn: psycopg2.extensions.connection) -> Tuple[str, Optional[str]]:
    """
    Validates the generated SQL against the schema and intent.
    Returns a potentially corrected SQL query and an error message if applicable.
    """
    print(f"Validating SQL query: {generated_sql}")
    corrected_sql = generated_sql
    error_message = None
    
    # Check if key filters from intent analysis are present in the SQL
    filters = intent_analysis.get("filters", {})
    for col, value in filters.items():
        # For each filter, check if it appears in the SQL
        value_pattern = rf"['\"]?{re.escape(str(value))}['\"]?"
        column_pattern = rf"\b{re.escape(col)}\b"
        
        if re.search(column_pattern, generated_sql, re.IGNORECASE):
            if not re.search(value_pattern, generated_sql, re.IGNORECASE):
                error_message = f"SQL query doesn't filter for '{value}' in column '{col}' as requested."
                print(error_message)
        else:
            error_message = f"SQL query doesn't include the column '{col}' as requested."
            print(error_message)
    
    # Check if tables from intent analysis are present in the SQL
    tables = intent_analysis.get("tables", [])
    for table in tables:
        table_pattern = rf"\b{re.escape(table)}\b"
        if not re.search(table_pattern, generated_sql, re.IGNORECASE):
            error_message = f"SQL query doesn't reference table '{table}' as expected."
            print(error_message)
    
    # Validate against actual database schema
    try:
        # Extract table names from the SQL query using regex
        table_pattern = r'FROM\s+(\w+)|JOIN\s+(\w+)'
        table_matches = re.findall(table_pattern, generated_sql, re.IGNORECASE)
        referenced_tables = [match[0] or match[1] for match in table_matches]
        
        # Check for nonexistent tables
        for table in referenced_tables:
            if table.lower() not in [t.lower() for t in schema.keys()]:
                error_message = f"SQL query references nonexistent table: {table}"
                print(error_message)
    
    except Exception as e:
        print(f"Error during SQL validation: {e}")
        traceback.print_exc()
    
    return corrected_sql, error_message

# --- SQL Repair Function ---
def repair_sql_query(generated_sql: str, schema_str: str, intent_analysis: Dict[str, Any], 
                    validation_error: str, llm: ChatGoogleGenerativeAI) -> Tuple[Optional[str], Optional[str]]:
    """
    Attempts to repair an invalid SQL query based on validation feedback.
    """
    if not llm:
        return generated_sql, "LLM not available for repair"
    
    repair_prompt = ChatPromptTemplate.from_messages([
        SystemMessage(
            content=f"""You are an expert PostgreSQL error fixer.
            Your task is to fix an invalid SQL query based on the error message and the database schema.

            Database Schema:
            {schema_str}

            Original SQL Query:
            {generated_sql}

            Error/Issue:
            {validation_error}

            User's Intent:
            {intent_analysis.get('correction', 'Unknown')}
            Tables likely needed: {', '.join(intent_analysis.get('tables', []))}
            Filters requested: {intent_analysis.get('filters', {})}

            Fix the SQL query to:
            1. Use only tables and columns that exist in the schema
            2. Include all the filters requested by the user
            3. Keep the query structure as close as possible to the original
            4. Return ONLY the fixed SQL query with no additional text
            """
        ),
        HumanMessage(content="Fix the SQL query:")
    ])
    
    # Using LCEL for the chain
    repair_chain = repair_prompt | llm | StrOutputParser()

    repaired_sql = None
    repair_error = None
    try:
        print("Attempting to repair SQL query...")
        repaired_sql_raw = repair_chain.invoke({})
        print(f"Repair result: '{repaired_sql_raw}'")

        # Clean up the repaired SQL
        sql_match = re.search(r'(SELECT\s+[\s\S]+;)', repaired_sql_raw, re.IGNORECASE | re.DOTALL)
        if sql_match:
            repaired_sql = sql_match.group(1).strip()
        else:
            # If no semicolon, take the whole response
            if "SELECT" in repaired_sql_raw.upper():
                repaired_sql = repaired_sql_raw.strip()
                if not repaired_sql.endswith(';'):
                    repaired_sql += ';'
            else:
                repair_error = "Repair failed: response doesn't contain a valid SQL query"
                repaired_sql = generated_sql

    except Exception as e:
        repair_error = f"Error during SQL repair: {e}"
        print(repair_error)
        traceback.print_exc()
        repaired_sql = generated_sql

    return repaired_sql, repair_error

# --- Main Pipeline Function ---
def run_sql_query_pipeline(user_query: str, db_config: Dict[str, str]) -> Dict[str, Any]:
    """
    Runs the full Text-to-SQL pipeline with a multi-stage approach:
    1. Analyze user intent and correct query
    2. Generate SQL based on intent
    3. Validate SQL against schema and intent
    4. Repair SQL if needed
    5. Execute SQL and return results
    """
    print(f"--- Starting SQL Pipeline for Query: '{user_query}' ---")
    pipeline_result = {
        "user_query": user_query,
        "corrected_query": None,
        "generated_sql": None,
        "query_results": None,
        "column_names": None,
        "error": None,
        "debug_info": {}
    }

    # 1. Get LLM Instance
    llm = get_google_llm()
    if not llm:
        pipeline_result["error"] = "LLM initialization failed. Check API Key setup."
        print(pipeline_result["error"])
        print("--- SQL Pipeline Finished (Error) ---")
        return pipeline_result

    # 2. Connect to Database (do this earlier to get schema and sample data)
    conn = get_db_connection(db_config)
    if not conn:
        pipeline_result["error"] = "Database connection failed."
        print(pipeline_result["error"])
        print("--- SQL Pipeline Finished (Error) ---")
        return pipeline_result

    try:
        # 3. Get actual schema and sample data
        schema = get_actual_schema(conn)
        schema_str = schema_to_formatted_string(schema)
        sample_data = get_sample_data(conn)
        
        # 4. Analyze user intent
        intent_analysis = analyze_user_intent(user_query, llm)
        if "error" in intent_analysis:
            print(f"Intent analysis warning: {intent_analysis['error']}")
            pipeline_result["debug_info"]["intent_error"] = intent_analysis["error"]
            # Continue anyway with limited information
        else:
            pipeline_result["corrected_query"] = intent_analysis.get("correction", user_query)
            pipeline_result["debug_info"]["intent_analysis"] = intent_analysis
        
        # 5. Generate SQL Query using LLM with intent guidance
        generated_sql, generation_error = generate_sql_query(
            user_query, intent_analysis, schema_str, sample_data, llm
        )
        
        if generation_error:
            pipeline_result["error"] = generation_error
            if "API_KEY_INVALID" in generation_error:
                print(f"Pipeline Error: {generation_error}")
                print("--- SQL Pipeline Finished (Error) ---")
                return pipeline_result
            # Continue if it was just a warning
            
        if not generated_sql:
            pipeline_result["error"] = "Failed to generate SQL query."
            print("--- SQL Pipeline Finished (Error) ---")
            return pipeline_result
            
        pipeline_result["generated_sql"] = generated_sql  # Store initial SQL
        
        # 6. Validate SQL against schema and intent
        validated_sql, validation_error = validate_sql_query(
            generated_sql, intent_analysis, schema, conn
        )
        
        if validation_error:
            pipeline_result["debug_info"]["validation_error"] = validation_error
            print(f"Validation Error: {validation_error}")
            
            # 7. Attempt to repair the SQL if validation failed
            repaired_sql, repair_error = repair_sql_query(
                generated_sql, schema_str, intent_analysis, validation_error, llm
            )
            
            if repair_error:
                pipeline_result["debug_info"]["repair_error"] = repair_error
            
            if repaired_sql != generated_sql:
                pipeline_result["debug_info"]["original_sql"] = generated_sql
                pipeline_result["generated_sql"] = repaired_sql
                generated_sql = repaired_sql
                print(f"SQL repaired: {repaired_sql}")
        
        # 8. Execute SQL Query
        query_results, column_names, db_error = execute_sql(conn, generated_sql)
        
        if db_error:
            pipeline_result["error"] = db_error
            pipeline_result["debug_info"]["execution_error"] = db_error
        else:
            pipeline_result["query_results"] = query_results
            pipeline_result["column_names"] = column_names
    
    except Exception as e:
        pipeline_result["error"] = f"Unexpected error in pipeline: {str(e)}"
        print(f"Pipeline exception: {e}")
        traceback.print_exc()
    
    finally:
        # 9. Close Database Connection
        if conn:
            conn.close()
            print("Database connection closed.")

    print(f"Pipeline Result Error Status: {pipeline_result['error']}")
    print("--- SQL Pipeline Finished ---")
    return pipeline_result