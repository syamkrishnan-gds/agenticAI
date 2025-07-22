from flask import Flask, request, render_template, Response, stream_with_context
import asyncio
from core.corelogic_api_flow import start_workflow

app = Flask(__name__)

@app.route('/')
def indexpage():
    return render_template('index.html')

@app.route('/start_agents', methods=['POST'])
def process_results():
    user_input = request.form.get('userText')
    return Response(stream_with_context(stream_response(user_input)), content_type='text/event-stream')
    #return render_template('result.html', message=Response(stream_with_context(stream_response(user_input)), content_type='text/event-stream'))

def stream_response(user_input):
    response = asyncio.run(start_workflow(user_input))
    content = response
    yield f"{content}\n"

if __name__ == '__main__':
    app.run(debug=True, threaded=True)