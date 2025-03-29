 
# app.py
import os
import traceback
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from utils import APP_CONFIG # Import pre-loaded config
from sql_pipeline import get_google_llm, run_sql_query_pipeline

app = Flask(__name__, template_folder='templates', static_folder='static')
app.config['SECRET_KEY'] = APP_CONFIG.get("flask_secret_key", "fallback-insecure-key")

# --- Flask Routes ---
@app.route('/')
def index():
    """Renders the main query input page."""
    # Clear previous results from session if desired
    return render_template('index.html')

@app.route('/save-api-keys', methods=['POST'])
def save_api_keys():
    """Saves Google API key to the session (Tavily not used)."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No data received.'}), 400

        gemini_key = data.get('gemini_api_key')

        if not gemini_key:
             return jsonify({'success': False, 'message': 'Google API Key is required.'}), 400

        session['GOOGLE_API_KEY'] = gemini_key

        print("Google API Key saved to session.")
        return jsonify({'success': True, 'message': 'API Key saved successfully.'})

    except Exception as e:
        print(f"Error saving API keys: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Server error: {e}'}), 500

@app.route('/ask', methods=['POST'])
def ask():
    """Handles the user's query, runs the pipeline, and redirects to results."""
    user_query = request.form.get('query')
    session_google_key = session.get('GOOGLE_API_KEY')

    # --- Validation ---
    if not user_query:
        flash('Please enter a question.', 'error')
        return redirect(url_for('index'))

    if not session_google_key and not APP_CONFIG.get('google_api_key'):
        flash('Google API Key is missing. Please configure API keys using the gear icon.', 'error')
        return redirect(url_for('index'))

    # --- Prepare Environment for Pipeline ---
    # Temporarily set API key in environment if provided via session
    original_google_key = os.environ.get("GOOGLE_API_KEY")
    temp_key_set = False
    if session_google_key:
        os.environ["GOOGLE_API_KEY"] = session_google_key
        temp_key_set = True
        print("Using Google API Key from session for this request.")
    elif APP_CONFIG.get('google_api_key'):
         # Key already loaded from .env, no need to set temporarily
         print("Using Google API Key from environment config.")
         pass # Key is already in env via initial load if available
    else:
        flash('API Key configuration error.', 'error')
        return redirect(url_for('index'))


    pipeline_result = {}
    try:
        # --- Run SQL Generation Pipeline ---
        print(f"Running pipeline for query: {user_query}")
        # Pass the database config loaded initially
        pipeline_result = run_sql_query_pipeline(user_query, APP_CONFIG)

    except Exception as e:
        # Catch unexpected errors during the pipeline's execution itself
        print(f"Unexpected error during pipeline execution: {e}")
        traceback.print_exc()
        flash(f"A critical error occurred: {e}", 'error')
        pipeline_result['error'] = f"A critical error occurred: {e}" # Ensure error is in result

    finally:
        # --- Restore Environment ---
        if temp_key_set: # Only restore if we set it temporarily
             if original_google_key:
                 os.environ["GOOGLE_API_KEY"] = original_google_key
                 print("Restored original Google API Key environment variable.")
             elif "GOOGLE_API_KEY" in os.environ:
                  # If it wasn't set before, remove the one we added
                  del os.environ["GOOGLE_API_KEY"]
                  print("Removed temporary Google API Key environment variable.")


    # --- Process Results ---
    error = pipeline_result.get('error')

    # Handle specific API key errors reported by the pipeline
    if error and "API_KEY_INVALID" in error:
        session.pop('GOOGLE_API_KEY', None) # Remove invalid key from session
        flash("The Google API key seems invalid. Please enter a valid key.", 'error')
        return redirect(url_for('index'))

    # Handle other errors
    if error:
        flash(f"Error processing your query: {error}", 'error')
        # Optionally store partial results if needed
        session['query_result'] = pipeline_result
        # If DB connection failed
        if "database connection failed" in error.lower():
             return redirect(url_for('index'))
        else:
             # Show partial results
             return redirect(url_for('result'))


    # --- Success ---
    if not error and pipeline_result.get("query_results") is not None:
         flash("Query processed successfully!", 'success')
         # Store the entire result dictionary in session for the result page
         session['query_result'] = pipeline_result
         return redirect(url_for('result'))
    elif not error and pipeline_result.get("generated_sql"):
         # Case where SQL was generated but maybe returned no results (valid)
         flash("Query processed, but no matching data found.", 'info')
         session['query_result'] = pipeline_result
         return redirect(url_for('result'))
    else:
         # Fallback if no specific error but no success state reached
         flash("Could not process the query.", 'warning')
         session['query_result'] = pipeline_result # Store anyway for debugging/display
         return redirect(url_for('result')) # Redirect to result page to show what happened


@app.route('/result')
def result():
    """Displays the results of the SQL query execution."""
    query_result = session.get('query_result') # Retrieve results from session

    if not query_result:
        # If session doesn't contain results, redirect to index
        flash("No query results found. Please ask a question first.", 'info')
        return redirect(url_for('index'))

    # Render the result template, passing the result dictionary
    return render_template('result.html', result=query_result)


# Keep the API key validation endpoint if using the UI modal
@app.route('/validate-api-key', methods=['POST'])
def validate_api_key():
    """Validates a provided Google API key by attempting a simple API call."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'valid': False, 'message': 'No data received.'})

        gemini_key = data.get('gemini_api_key')

        if not gemini_key:
            return jsonify({'valid': False, 'message': 'No API key provided.'})

        # Temporarily set env var for validation call
        original_key = os.environ.get("GOOGLE_API_KEY")
        os.environ["GOOGLE_API_KEY"] = gemini_key
        temp_key_set_validation = True

        is_valid = False
        validation_message = "Unknown validation error."
        validator_llm = None

        try:
            # initialize the LLM
            validator_llm = get_google_llm()
            if validator_llm:
                is_valid = True
                validation_message = 'API key seems valid (initialization successful).'
            else:
                 # get_google_llm prints errors, capture the message if possible
                 validation_message = 'API key initialization failed (likely invalid).'


        except Exception as e:
            error_message_str = str(e)
            print(f"API Key Validation Error: {error_message_str}")
            if "API key not valid" in error_message_str or "API_KEY_INVALID" in error_message_str:
                is_valid = False
                validation_message = 'The provided API key is invalid.'
            else:
                is_valid = False
                validation_message = f'Error testing API key: Check console logs.' # Keep message generic

        finally:
            # Restore environment
            if temp_key_set_validation:
                if original_key:
                    os.environ["GOOGLE_API_KEY"] = original_key
                elif "GOOGLE_API_KEY" in os.environ:
                    del os.environ["GOOGLE_API_KEY"]

        return jsonify({'valid': is_valid, 'message': validation_message})

    except Exception as e:
        print(f"Server error during API key validation: {e}")
        traceback.print_exc()
        return jsonify({'valid': False, 'message': f'Server error: {str(e)}'})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5010, debug=True)