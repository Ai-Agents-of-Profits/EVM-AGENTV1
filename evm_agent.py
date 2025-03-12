#!/usr/bin/env python3
"""
EVM DeFi Agent

This script connects to the EVM signer MCP server to provide a secure interface
for managing Ethereum wallets and interacting with DeFi protocols.
"""

import os
import sys
import json
import asyncio
import platform
import time
import traceback
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up OpenAI client
from openai import AsyncOpenAI

# Configure OpenAI from environment variables
api_key = os.getenv("OPENAI_API_KEY")
base_url = os.getenv("OPENAI_API_BASE")  # Optional base URL override

# Initialize AsyncOpenAI client with proper configuration
client = AsyncOpenAI(
    api_key=api_key,
    base_url=base_url,  # Will be None if not set in environment
    timeout=60.0,  # Increased timeout to 60 seconds
)

# Constants
MODEL_ID = os.getenv("LLM_MODEL", "gpt-4")  # Use environment variable with fallback
TOOL_CALL_TIMEOUT = 120  # 120 seconds timeout for tool calls
INITIALIZATION_TIMEOUT = 30  # 30 seconds timeout for server initialization

# MCP imports
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# System prompt for the EVM DeFi agent
SYSTEM_PROMPT = """You are an EVM DeFi agent that helps users manage their wallets and interact with DeFi protocols.

Current Wallet State:
{wallet_state}

Active Wallet: 0x95723432b6a145b658995881b0576d1e16850b02
Network: monad-testnet

Available tools:
{tools}

Please assist the user with their wallet management and DeFi operations. Always use the active wallet address when making tool calls."""


class MCPClient:
    """A client class for interacting with the EVM signer MCP server."""
    def __init__(self, server_params: StdioServerParameters):
        self.server_params = server_params
        self.session = None
        self._client = None
        self.tools = {}

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        try:
            if self.session:
                await self.session.__aexit__(exc_type, exc_val, exc_tb)
        except Exception as e:
            print(f"Error closing session: {str(e)}")
            
        try:
            if self._client:
                await self._client.__aexit__(exc_type, exc_val, exc_tb)
        except Exception as e:
            print(f"Error closing client: {str(e)}")

    async def connect(self):
        """Establishes connection to MCP server"""
        print("Connecting to EVM signer MCP server...")
        self._client = stdio_client(self.server_params)
        print("DEBUG: Created stdio_client")
        self.read, self.write = await self._client.__aenter__()
        print("DEBUG: Got read/write streams")
        session = ClientSession(self.read, self.write)
        print("DEBUG: Created ClientSession")
        self.session = await session.__aenter__()
        print("DEBUG: Entered session")
        
        try:
            print(f"DEBUG: Starting initialization with {INITIALIZATION_TIMEOUT}s timeout")
            initialization_task = asyncio.create_task(self.session.initialize())
            await asyncio.wait_for(initialization_task, timeout=INITIALIZATION_TIMEOUT)
            print("DEBUG: Initialized session")
            print("MCP EVM Signer server running on stdio")
        except asyncio.TimeoutError:
            print(f"ERROR: Timeout while initializing MCP server after {INITIALIZATION_TIMEOUT} seconds")
            print("The server might be stuck. Some features may not work properly.")

    async def get_available_tools(self) -> Dict[str, Any]:
        """Retrieve available tools from the MCP server."""
        if not self.session:
            raise RuntimeError("Not connected to MCP server")

        try:
            print("DEBUG: Getting tools from MCP server...")
            tools_task = asyncio.create_task(self.session.list_tools())
            try:
                tools_response = await asyncio.wait_for(tools_task, timeout=INITIALIZATION_TIMEOUT)
                print("DEBUG: Got tools response")
                
                tools_list = tools_response.tools
                print(f"DEBUG: Extracted {len(tools_list)} tools")
                
                for tool in tools_list:
                    tool_name = tool.name
                    
                    schema = {
                        "type": "function",
                        "function": {
                            "name": tool_name,
                            "description": tool.description if hasattr(tool, 'description') else "",
                            "parameters": tool.parameters if hasattr(tool, 'parameters') else {}
                        }
                    }
                    
                    self.tools[tool_name] = {
                        "name": tool_name,
                        "schema": schema,
                        "callable": self.call_tool(tool_name)
                    }
                    
                    # Store with underscores instead of hyphens for compatibility
                    alt_name = tool_name.replace("-", "_")
                    if alt_name != tool_name:
                        self.tools[alt_name] = self.tools[tool_name]
                
                print(f"Loaded {len(tools_list)} tools from MCP server")
                return self.tools
            except asyncio.TimeoutError:
                print(f"ERROR: Timeout getting tools after {INITIALIZATION_TIMEOUT} seconds")
                return {}
                
        except Exception as e:
            print(f"Error getting tools: {str(e)}")
            traceback.print_exc()
            return {}

    def call_tool(self, tool_name: str) -> Any:
        """Create a callable function for a specific tool."""
        if not self.session:
            raise RuntimeError("Not connected to MCP server")

        async def callable(*args, **kwargs):
            max_retries = 3
            retry_delay = 5  # seconds
            
            for attempt in range(max_retries):
                try:
                    print(f"DEBUG: Calling tool {tool_name} (attempt {attempt + 1}/{max_retries}) with args {kwargs}")
                    tool_task = asyncio.create_task(self.session.call_tool(tool_name, arguments=kwargs))
                    
                    try:
                        response = await asyncio.wait_for(tool_task, timeout=TOOL_CALL_TIMEOUT)
                        print(f"DEBUG: Got response from tool {tool_name}")
                        # Simply return the raw response without parsing
                        return response
                    except asyncio.TimeoutError:
                        print(f"DEBUG: Timeout after {TOOL_CALL_TIMEOUT} seconds for {tool_name}")
                        if attempt < max_retries - 1:
                            print(f"Retrying in {retry_delay} seconds...")
                            await asyncio.sleep(retry_delay)
                            continue
                        return {"error": f"Operation timed out after {max_retries} attempts"}
                except Exception as e:
                    print(f"Error calling {tool_name}: {str(e)}")
                    if attempt < max_retries - 1:
                        print(f"Retrying in {retry_delay} seconds...")
                        await asyncio.sleep(retry_delay)
                        continue
                    traceback.print_exc()
                    return {"error": str(e)}

        return callable

async def get_wallet_state(mcp_client):
    """Get current wallet state."""
    return {
        "wallets": [],
        "balances": {},
        "positions": {}
    }

async def extract_tool_result(response, tool_name: str):
    """Extract the actual result from a MCP server response."""
    print(f"Extracting result for {tool_name}...")
    
    try:
        # Handle JSON-RPC response structure
        if isinstance(response, dict) and "result" in response:
            if isinstance(response["result"], dict) and "content" in response["result"]:
                content = response["result"]["content"]
                if isinstance(content, list) and len(content) > 0 and "text" in content[0]:
                    try:
                        # Try to parse as JSON
                        return json.loads(content[0]["text"])
                    except:
                        # Return as text if not valid JSON
                        return content[0]["text"]
                return content
            return response["result"]
        return response
    except Exception as e:
        print(f"Error extracting result: {e}")
        return response

async def execute_tool_with_timeout(tool_callable, arguments, timeout=10):
    """Execute a tool with a timeout to prevent hanging."""
    try:
        # Create a task for the tool execution
        task = asyncio.create_task(tool_callable(**arguments))
        
        # Wait for the task to complete with a timeout
        result = await asyncio.wait_for(task, timeout=timeout)
        return result, None
    except asyncio.TimeoutError:
        return None, f"Tool execution timed out after {timeout} seconds"
    except Exception as e:
        return None, f"Error executing tool: {str(e)}"

async def agent_loop(query: str, mcp_tools: dict, wallet_state: dict, messages: List[dict] = None):
    """
    Main agent loop with a clean flow:
    User Query -> LLM Tool Selection -> Tool Execution -> LLM Summary -> Response
    """
    if messages is None:
        messages = []

    try:
        # STEP 1: Initialize conversation if empty
        if not messages:
            # System message
            messages.append({
                "role": "system",
                "content": (
                    "You are a helpful DeFi assistant that can interact with EVM blockchains. "
                    "Use the available tools to help users manage their finances and investments."
                )
            })

        # Create a copy of messages to work with
        current_messages = messages.copy()
        
        # STEP 2: Add user query
        current_messages.append({"role": "user", "content": query})
        print(f"\nProcessing user query: {query}")

        # STEP 3: First LLM call - Ask LLM to select tools
        print("\nAsking LLM to select appropriate tools...")
        first_response = await client.chat.completions.create(
            model=MODEL_ID,
            messages=current_messages,
            tools=[tool["schema"] for tool in mcp_tools.values()],
            tool_choice="auto"
        )
        
        assistant_message = first_response.choices[0].message
        
        # Check if the response includes tool calls
        if not hasattr(assistant_message, 'tool_calls') or not assistant_message.tool_calls:
            print("No tool calls requested. Returning direct LLM response.")
            # Add assistant's response to the conversation history
            messages.append({"role": "assistant", "content": assistant_message.content or ""})
            return assistant_message.content, messages
        
        # Add user query to permanent history
        messages.append({"role": "user", "content": query})
        
        # Format the assistant message with tool calls for the API
        assistant_with_tools = {
            "role": "assistant",
            "content": assistant_message.content or "",
            "tool_calls": []
        }
        
        # Format tool calls in the correct structure for the API
        for tool_call in assistant_message.tool_calls:
            assistant_with_tools["tool_calls"].append({
                "id": tool_call.id,
                "type": "function",
                "function": {
                    "name": tool_call.function.name,
                    "arguments": tool_call.function.arguments
                }
            })
        
        # Add the assistant message with tool calls to the permanent history
        messages.append(assistant_with_tools)
            
        # STEP 4: Tool Execution Phase
        print("\nExecuting requested tools...")
        tool_results = []
        
        for tool_call in assistant_message.tool_calls:
            function_name = tool_call.function.name
            print(f"\nProcessing tool call: {function_name}")
            
            # Parse tool arguments
            try:
                arguments = json.loads(tool_call.function.arguments)
            except:
                arguments = {}
                
            # Add default values if needed
            if function_name in ["get-user-position", "check-balance", "get-lending-balance", 
                                  "get-borrow-balance", "get-collateral-balance"]:
                if "address" not in arguments:
                    arguments["address"] = "0x95723432b6a145b658995881b0576d1e16850b02"
            
            # Always set network to monad-testnet
            arguments["network"] = "monad-testnet"
            
            print(f"Tool arguments: {json.dumps(arguments, indent=2)}")
            
            # Execute the tool if available
            if function_name in mcp_tools:
                print(f"Executing {function_name}...")
                
                start_time = time.time()
                error_msg = None
                
                # Execute the tool with a timeout
                if function_name == "get-user-position":
                    # Use a longer timeout for position data which might take longer
                    raw_result, error = await execute_tool_with_timeout(
                        mcp_tools[function_name]["callable"], 
                        arguments,
                        timeout=60  # Increased timeout for position data (was 30)
                    )
                else:
                    # Standard timeout for other tools
                    raw_result, error = await execute_tool_with_timeout(
                        mcp_tools[function_name]["callable"], 
                        arguments,
                        timeout=15
                    )
                
                execution_time = time.time() - start_time
                print(f"Tool execution completed in {execution_time:.2f} seconds")
                
                if error:
                    # Handle timeout or execution error
                    error_msg = error
                    print(f"Tool execution failed: {error_msg}")
                    
                    # Add error as tool response
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": function_name,
                        "content": json.dumps({"error": error_msg}),
                    })
                    tool_results.append({"tool": function_name, "error": error_msg})
                    continue
                
                try:
                    # Check if raw_result is None or empty
                    if raw_result is None:
                        error_msg = f"No response received from {function_name} tool"
                        print(error_msg)
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": json.dumps({"error": error_msg})
                        })
                        tool_results.append({"tool": function_name, "error": error_msg})
                        continue
                    
                    # --- REPLACED CODE BLOCK START ---
                    # Handle the MCP response based on its known structure
                    try:
                        # The MCP response structure based on inspection:
                        # { "content": [{"type": "text", "text": "JSON string"}], "isError": false }
                        if hasattr(raw_result, 'content') and isinstance(raw_result.content, list):
                            # This is the typical MCP response structure
                            if raw_result.content and hasattr(raw_result.content[0], 'text'):
                                tool_message_content = raw_result.content[0].text
                            else:
                                tool_message_content = str(raw_result.content)
                        elif hasattr(raw_result, 'text'):
                            # Direct text content
                            tool_message_content = raw_result.text
                        else:
                            # Fallback for any other format
                            try:
                                tool_message_content = json.dumps(raw_result) if not isinstance(raw_result, str) else raw_result
                            except:
                                # Last resort - string representation
                                tool_message_content = str(raw_result)
                        
                        # -- INSERTED NORMALIZATION SNIPPET START --
                        # Normalize JSON to ensure it's clean and properly formatted for the API
                        try:
                            # If it's a JSON string, parse it and re-stringify to normalize
                            json_obj = json.loads(tool_message_content)
                            tool_message_content = json.dumps(json_obj, ensure_ascii=False)
                        except:
                            # If it's not valid JSON, leave it as is
                            pass
                        # -- INSERTED NORMALIZATION SNIPPET END --

                        
                        
                        print(f"DEBUG: Sending MCP response to LLM: content={tool_message_content[:200] if len(str(tool_message_content)) > 200 else tool_message_content}...")
                        
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": tool_message_content
                        })
                        tool_results.append({"tool": function_name, "result": "Result processed successfully"})
                    except Exception as e:
                        print(f"Error processing MCP result: {str(e)}")
                        traceback.print_exc()
                        tool_message_content = str(raw_result)
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": tool_message_content
                        })
                    # --- REPLACED CODE BLOCK END ---
                    
                except Exception as e:
                    error_msg = f"Error processing tool result: {str(e)}"
                    print(error_msg)
                    traceback.print_exc()
                    
                    # Add error as tool response
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps({"error": error_msg})
                    })
                    tool_results.append({"tool": function_name, "error": error_msg})
            else:
                error_msg = f"Tool {function_name} not found"
                print(error_msg)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps({"error": error_msg})
                })
                tool_results.append({"tool": function_name, "error": error_msg})
        
        # STEP 5: Final LLM call - Generate summary response
        print("\nGenerating final response...")
        
        # Debug the message structure before sending
        print(f"Message count: {len(messages)}")
        for i, msg in enumerate(messages):
            print(f"Message {i}: role={msg['role']}{' with tool_calls' if 'tool_calls' in msg else ''}")
        
        # Make the final API call
        try:
            final_response = await client.chat.completions.create(
                model=MODEL_ID,
                messages=messages,
            )
            
            final_content = final_response.choices[0].message.content
            messages.append({"role": "assistant", "content": final_content})
            
            return final_content, messages
        except Exception as e:
            error_message = f"Error in final LLM call: {str(e)}"
            print(error_message)
            traceback.print_exc()
            
            # Try with a simplified conversation if there was an error
            print("Trying with simplified conversation...")
            simplified_messages = [
                messages[0],  # system message
                messages[1],  # user query
                {"role": "assistant", "content": "I processed your request and here's what I found:"}
            ]
            
            for result in tool_results:
                if "result" in result:
                    simplified_messages[-1]["content"] += f"\n\nFor tool {result['tool']}, I found: {json.dumps(result['result'], indent=2)}"
                else:
                    simplified_messages[-1]["content"] += f"\n\nTool {result['tool']} encountered an error: {result['error']}"
            
            return simplified_messages[-1]["content"], simplified_messages
        
    except Exception as e:
        error_message = f"Error in agent loop: {str(e)}"
        print(error_message)
        traceback.print_exc()
        
        # Generate a simple fallback response
        fallback_response = "I encountered an error while processing your request. Please try again or rephrase your question."
        return fallback_response, messages




async def main():
    """Main function that sets up the MCP server and runs the interactive agent."""
    start_time = time.time()
    
    if platform.system() == 'Windows':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    # Configure EVM signer MCP server using Docker
    server_params = StdioServerParameters(
        command="docker",
        args=[
            "run",
            "--rm",  # Remove container after exit
            "-i",    # Interactive mode
            "-v", "mcp-evm-src:/app/src",  # Mount source code
            "-v", "mcp-evm-keys:/app/keys",  # Mount keys directory
            "-e", f"ALCHEMY_API_KEY={os.getenv('ALCHEMY_API_KEY', '')}",
            "-e", "DEFAULT_NETWORK=monad-testnet",
            "-e", "ENCRYPT_KEYS=true",
            "-e", "KEY_PASSWORD=aop",
            "--name", "mcp-evm-signer",
            "evm-signer-mcp"
        ],
        env=None
    )
    
    try:
        print("Starting MCP client...")
        async with MCPClient(server_params) as mcp_client:
            # Get available tools
            print("Getting available tools...")
            mcp_tools = await mcp_client.get_available_tools()
            
            print(f"Loaded {len(mcp_tools)} tools from MCP server")
            
            # Welcome message
            print("\n" + "="*80)
            print("EVM DeFi Agent")
            print("="*80)
            print("Type your instructions for wallet management or DeFi operations.")
            print("Type 'quit', 'exit', or 'q' to exit the program.")
            print("="*80 + "\n")
            
            if len(mcp_tools) == 0:
                print("⚠️ WARNING: No tools loaded from MCP server. Functionality will be limited.")
            else:
                print("✅ MCP server connected successfully.")
            
            # Track startup time
            total_startup_time = time.time() - start_time
            print(f"Startup completed in {total_startup_time:.2f} seconds\n")
            
            # Check OpenAI connectivity
            try:
                test_response = await client.chat.completions.create(
                    model=MODEL_ID,
                    messages=[{"role": "user", "content": "Hello"}],
                    max_tokens=5
                )
                print("✅ OpenAI API connection successful\n")
            except Exception as e:
                print(f"⚠️ WARNING: Could not connect to OpenAI API: {str(e)}")
                print("Some functionality may be limited. Direct tool calls will still work.\n")
            
            # Interactive loop
            messages = None
            while True:
                try:
                    user_input = input("Enter your instruction: ")
                    
                    if user_input.lower() in ["quit", "exit", "q"]:
                        print("Exiting...")
                        break
                    
                    # Direct tool calls for debugging
                    if user_input.startswith("!tool "):
                        parts = user_input[6:].split(" ", 1)
                        tool_name = parts[0]
                        args_str = parts[1] if len(parts) > 1 else "{}"
                        
                        try:
                            args = json.loads(args_str)
                            print(f"Directly calling tool: {tool_name} with args: {args}")
                            
                            if tool_name in mcp_tools:
                                tool_result = await mcp_tools[tool_name]["callable"](**args)
                                print(f"\nResult: {json.dumps(tool_result, indent=2)}\n")
                            else:
                                print(f"Tool {tool_name} not found")
                            continue
                        except Exception as e:
                            print(f"Error calling tool directly: {str(e)}")
                            traceback.print_exc()
                            continue
                    
                    # Log timestamp
                    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Processing...")
                    
                    # Get current wallet state
                    wallet_state = await get_wallet_state(mcp_client)
                    
                    # Process query through agent loop
                    response, messages = await agent_loop(
                        user_input,
                        mcp_tools,
                        wallet_state,
                        messages
                    )
                    
                    print(f"\nResponse: {response}\n")
                    
                except KeyboardInterrupt:
                    print("\nExiting...")
                    break
                except Exception as e:
                    print(f"\nError: {str(e)}")
                    traceback.print_exc()

    except Exception as e:
        print(f"Error in main execution: {str(e)}")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
