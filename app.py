import os
import json
import asyncio
import platform
import traceback
import threading
import time
from flask import Flask, render_template, request, jsonify
from evm_agent import agent_loop, MCPClient, StdioServerParameters

app = Flask(__name__, 
            static_folder='static',
            template_folder='templates')

# Global variables to store agent state
mcp_client = None
mcp_tools = None
wallet_state = {"network": "monad-testnet"}
conversation_history = []
loop = None
initialization_complete = False

async def load_mcp_config():
    """Load the MCP server configuration from mcp_config.json"""
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mcp_config.json")
    try:
        with open(config_path, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading MCP config: {e}")
        return {"mcpServers": {}}

async def initialize_mcp_client():
    """Initialize the MCP client and get available tools."""
    global mcp_client, mcp_tools, initialization_complete
    
    if platform.system() == 'Windows':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    try:
        # Load configuration from JSON file
        config = await load_mcp_config()
        print("MCP config loaded successfully")
        
        # Initialize MCP client based on config
        if "evm-signer" in config.get("mcpServers", {}):
            server_config = config["mcpServers"]["evm-signer"]
            
            # Resolve environment variables in args
            resolved_args = []
            for arg in server_config["args"]:
                if isinstance(arg, str) and "${" in arg:
                    # Simple environment variable substitution
                    for env_var in os.environ:
                        placeholder = "${" + env_var + "}"
                        if placeholder in arg:
                            arg = arg.replace(placeholder, os.environ[env_var])
                resolved_args.append(arg)
            
            # Create server parameters
            server_params = StdioServerParameters(
                command=server_config["command"],
                args=resolved_args,
                env=server_config.get("env")
            )
            
            print("Starting MCP client...")
            mcp_client = MCPClient(server_params)
            await mcp_client.__aenter__()
            
            # Get available tools
            print("Getting available tools...")
            mcp_tools = await mcp_client.get_available_tools()
            print(f"Loaded {len(mcp_tools)} tools from MCP server")
            initialization_complete = True
            return mcp_tools
        else:
            print("No evm-signer configuration found in mcp_config.json")
            return []
    except Exception as e:
        print(f"Error in initialize_mcp_client: {str(e)}")
        traceback.print_exc()
        initialization_complete = True
        return []

def run_async(coro):
    """Helper function to run async code from sync context"""
    return asyncio.run_coroutine_threadsafe(coro, loop).result()

def start_background_loop(loop):
    """Set event loop in the current thread and run it forever"""
    asyncio.set_event_loop(loop)
    loop.run_forever()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/status', methods=['GET'])
def get_status():
    """API endpoint to check the status of the server and MCP client"""
    return jsonify({
        "status": "running",
        "mcp_client_initialized": mcp_tools is not None and len(mcp_tools) > 0,
        "tools_count": len(mcp_tools) if mcp_tools else 0,
        "initialization_complete": initialization_complete
    })

@app.route('/api/query', methods=['POST'])
def process_query():
    global mcp_tools, wallet_state, conversation_history
    
    data = request.json
    query = data.get('query', '')
    
    if not query:
        return jsonify({"error": "No query provided"}), 400
    
    # Check if MCP client is initialized
    if mcp_tools is None or len(mcp_tools) == 0:
        if initialization_complete:
            return jsonify({
                "response": "I'm having trouble connecting to the blockchain tools. You can still chat with me, but I won't be able to execute any blockchain operations.",
                "tool_calls": []
            })
        else:
            return jsonify({
                "response": "The system is still initializing. Please try again in a moment.",
                "tool_calls": []
            })
    
    # Process the query through the agent
    try:
        start_time = time.time()
        
        # Process the query asynchronously
        async def process():
            return await agent_loop(query, mcp_tools, wallet_state, conversation_history.copy() if conversation_history else None)
            
        # Run the agent loop in the event loop
        response, updated_messages = run_async(process())
        
        processing_time = time.time() - start_time
        print(f"Query processed in {processing_time:.2f} seconds")
        
        # Update conversation history
        conversation_history = updated_messages
        
        # Get tool calls for display - only if they actually exist and are not empty
        tool_calls = []
        has_valid_tool_calls = False
        
        for msg in updated_messages:
            if msg.get('role') == 'assistant' and 'tool_calls' in msg and msg['tool_calls']:
                for tool_call in msg.get('tool_calls', []):
                    function_info = tool_call.get('function', {})
                    tool_info = {
                        'name': function_info.get('name', ''),
                        'arguments': function_info.get('arguments', '{}')
                    }
                    
                    # Only add non-empty tool calls
                    if tool_info['name']:
                        has_valid_tool_calls = True
                        tool_calls.append(tool_info)
        
        response_data = {
            "response": response,
            "processing_time": f"{processing_time:.2f}"
        }
        
        # Only include tool_calls if there are actually valid ones
        if has_valid_tool_calls:
            response_data["tool_calls"] = tool_calls
        
        return jsonify(response_data)
    except Exception as e:
        print(f"Error processing query: {str(e)}")
        traceback.print_exc()
        return jsonify({"error": f"Error processing query: {str(e)}"}), 500

@app.route('/api/reset', methods=['POST'])
def reset_conversation():
    global conversation_history
    conversation_history = []
    return jsonify({"status": "success", "message": "Conversation reset successfully"})

if __name__ == '__main__':
    # Create a new event loop for async operations
    loop = asyncio.new_event_loop()
    
    # Start the loop in a background thread
    t = threading.Thread(target=start_background_loop, args=(loop,))
    t.daemon = True
    t.start()
    
    # Initialize MCP client in the background loop
    future = asyncio.run_coroutine_threadsafe(initialize_mcp_client(), loop)
    
    # Run Flask app in the main thread (don't wait for initialization to complete)
    app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False)