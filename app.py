# ============================================================================
# Faraz ye Man - Immortal Notebook
# Backend: Flask + SocketIO + Notebook Management + Code Execution
# ============================================================================

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
import json
import traceback
from pathlib import Path
import sys
import io
from contextlib import redirect_stdout, redirect_stderr

# Configuration
app = Flask(__name__)
app.config['SECRET_KEY'] = 'faraz-ye-man-immortal-secret'
socketio = SocketIO(app, cors_allowed_origins="*")

NOTEBOOKS_DIR = Path('./notebooks')
NOTEBOOKS_DIR.mkdir(exist_ok=True)

# Persistent execution contexts (per session)
execution_contexts = {}

def get_notebook_path(name: str) -> Path:
    safe_name = "".join(c for c in name if c.isalnum() or c in (' ', '-', '_')).strip()
    return NOTEBOOKS_DIR / f"{safe_name}.json"

# ============================================================================
# API Routes
# ============================================================================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/notebooks', methods=['GET'])
def list_notebooks():
    notebooks = []
    for nb_file in NOTEBOOKS_DIR.glob('*.json'):
        notebooks.append({'name': nb_file.stem})
    return jsonify(notebooks)

@app.route('/api/notebooks/<name>', methods=['GET'])
def get_notebook(name):
    path = get_notebook_path(name)
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            return jsonify(json.load(f))
    return jsonify({'cells': [], 'metadata': {'name': name}})

@app.route('/api/notebooks/<name>', methods=['POST'])
def save_notebook(name):
    data = request.json
    path = get_notebook_path(name)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    return jsonify({'success': True})

# ============================================================================
# WebSocket Handlers
# ============================================================================

@socketio.on('connect')
def handle_connect():
    session_id = request.sid
    execution_contexts[session_id] = {'globals': {}, 'locals': {}}
    emit('connected', {'session_id': session_id})

@socketio.on('execute_cell')
def handle_execute_cell(data):
    session_id = request.sid
    code = data.get('code', '')
    cell_id = data.get('cell_id', '')

    # Get or create context
    if session_id not in execution_contexts:
        execution_contexts[session_id] = {'globals': {}, 'locals': {}}

    ctx = execution_contexts[session_id]

    # Capture output
    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()

    result = {
        'cell_id': cell_id,
        'success': True,
        'output': '',
        'error': None
    }

    # Custom input function that asks frontend for input
    def custom_input(prompt=""):
        # Send input request to frontend
        emit('input_request', {
            'cell_id': cell_id,
            'prompt': prompt
        })

        # Wait for user's input response (blocking)
        # Store the response in a list so we can access it from callback
        user_input = []

        def on_input_response(response_data):
            if response_data.get('cell_id') == cell_id:
                user_input.append(response_data.get('value', ''))

        # Register temporary listener
        socketio.on_event('input_response', on_input_response)

        # Wait for response (with timeout)
        import time
        timeout = 30  # 30 seconds
        elapsed = 0
        while not user_input and elapsed < timeout:
            socketio.sleep(0.1)
            elapsed += 0.1

        if not user_input:
            raise TimeoutError("Input timeout - no response received")

        return user_input[0]

    try:
        # Add custom input to the execution context
        ctx['globals']['input'] = custom_input

        with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
            exec(code, ctx['globals'], ctx['locals'])

        output = stdout_capture.getvalue()
        if output:
            result['output'] = output
        else:
            result['output'] = '✓ Executed successfully'

    except Exception as e:
        result['success'] = False
        result['error'] = {
            'type': type(e).__name__,
            'message': str(e),
            'traceback': traceback.format_exc()
        }

    emit('execution_result', result)

@socketio.on('reset_kernel')
def handle_reset_kernel():
    session_id = request.sid
    execution_contexts[session_id] = {'globals': {}, 'locals': {}}
    emit('kernel_reset', {'success': True})

@socketio.on('disconnect')
def handle_disconnect():
    session_id = request.sid
    if session_id in execution_contexts:
        del execution_contexts[session_id]

# ============================================================================
# Main Entry
# ============================================================================

if __name__ == '__main__':
    # Create default notebook
    default_path = get_notebook_path('Welcome')
    if not default_path.exists():
        default_content = {
            'metadata': {'name': 'Welcome'},
            'cells': [
                {'type': 'markdown', 'content': '# 🚀 Welcome to Faraz ye Man\n\nYour immortal notebook is ready!'},
                {'type': 'code', 'content': 'print("Hello from Faraz ye Man!")\nfor i in range(3):\n    print(f"✨ Line {i}")'}
            ]
        }
        with open(default_path, 'w') as f:
            json.dump(default_content, f, indent=2)
    
    print("=" * 70)
    print("🚀 Faraz ye Man - Immortal Notebook")
    print("=" * 70)
    print("Server running on: http://127.0.0.1:5000")
    print("Press Ctrl+C to stop")
    print("=" * 70)
    
    socketio.run(app, host='127.0.0.1', port=5000, debug=True)
