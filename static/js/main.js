// Initialize marked.js with proper options
marked.setOptions({
    breaks: true,
    gfm: true,
    headerIds: false,
    highlight: function(code, language) {
        return code;
    }
});

document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const queryForm = document.getElementById('query-form');
    const queryInput = document.getElementById('query-input');
    const conversationContainer = document.getElementById('conversation');
    const loadingOverlay = document.getElementById('loading-overlay');
    const resetButton = document.getElementById('reset-conversation');
    const querySuggestions = document.querySelectorAll('.query-suggestion');
    const sidebarToggle = document.getElementById('sidebar-toggle');
    const sidebar = document.getElementById('sidebar');
    const mainContent = document.getElementById('main-content');
    
    // Set default wallet info
    document.getElementById('wallet-address').textContent = 
        '0x95723432b6a145b658995881b0576d1e16850b02';

    // Check server status
    checkServerStatus();
    
    // Initialize sidebar state based on screen size
    initializeSidebarState();
    
    // Handle sidebar toggle
    sidebarToggle.addEventListener('click', toggleSidebar);
    
    // Close sidebar when clicking on main content on mobile
    mainContent.addEventListener('click', function(e) {
        if (window.innerWidth < 992 && !document.body.classList.contains('sidebar-hidden')) {
            toggleSidebar();
        }
    });
    
    // Handle form submission
    queryForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const query = queryInput.value.trim();
        if (!query) return;
        
        // Add user message to the conversation
        addMessage('user', query);
        
        // Clear input
        queryInput.value = '';
        
        // Show loading indicator
        loadingOverlay.classList.remove('d-none');
        
        try {
            const response = await fetch('/api/query', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ query }),
            });
            
            const data = await response.json();
            
            if (response.ok) {
                // Display tool calls if available
                if (data.tool_calls && data.tool_calls.length > 0) {
                    addToolCalls(data.tool_calls);
                }
                
                // Add assistant message with the response
                addMessage('assistant', data.response);
            } else {
                // Handle error
                addMessage('system', 'Error: ' + (data.error || 'Something went wrong. Please try again.'));
            }
        } catch (error) {
            console.error('Error:', error);
            addMessage('system', 'Error: Could not connect to the server. Please try again later.');
        } finally {
            // Hide loading indicator
            loadingOverlay.classList.add('d-none');
        }
    });
    
    // Handle reset button
    resetButton.addEventListener('click', async () => {
        try {
            const response = await fetch('/api/reset', {
                method: 'POST',
            });
            
            if (response.ok) {
                // Clear conversation container
                conversationContainer.innerHTML = '';
                
                // Add welcome message
                addMessage('system', 'Conversation has been reset. Ask me about your wallet, token positions, market data, or any DeFi operations you\'d like to perform.');
            }
        } catch (error) {
            console.error('Error resetting conversation:', error);
        }
    });
    
    // Handle query suggestions
    querySuggestions.forEach(suggestion => {
        suggestion.addEventListener('click', () => {
            queryInput.value = suggestion.textContent;
            queryForm.dispatchEvent(new Event('submit'));
        });
    });
    
    // Function to check server status
    async function checkServerStatus() {
        try {
            const response = await fetch('/api/status');
            
            if (response.ok) {
                const data = await response.json();
                
                if (!data.mcp_client_initialized) {
                    // If MCP client is not initialized, show a warning
                    addMessage('system', '⚠️ **Warning**: The MCP client is not initialized. Some functionality may be limited or unavailable.');
                    document.getElementById('wallet-network').innerHTML = 'Network: <span class="badge bg-warning">Disconnected</span>';
                } else {
                    document.getElementById('wallet-network').innerHTML = 'Network: <span class="badge bg-success">Monad Testnet</span>';
                }
            }
        } catch (error) {
            console.error('Error checking server status:', error);
            addMessage('system', '⚠️ **Warning**: Could not connect to the server. Some functionality may be limited or unavailable.');
        }
    }
    
    // Function to add a message to the conversation
    function addMessage(role, content) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${role}-message`;
        
        const messageContent = document.createElement('div');
        messageContent.className = 'message-content';
        
        // Process markdown in content if it's from the assistant
        if (role === 'assistant' || role === 'system') {
            messageContent.innerHTML = marked.parse(content);
        } else {
            messageContent.innerHTML = `<p>${escapeHtml(content)}</p>`;
        }
        
        messageDiv.appendChild(messageContent);
        conversationContainer.appendChild(messageDiv);
        
        // Scroll to the bottom
        conversationContainer.scrollTop = conversationContainer.scrollHeight;
    }
    
    // Function to add tool calls to the conversation
    function addToolCalls(toolCalls) {
        const toolCallsDiv = document.createElement('div');
        toolCallsDiv.className = 'message system-message';
        
        const toolCallsContent = document.createElement('div');
        toolCallsContent.className = 'message-content';
        
        // More compact heading
        let toolCallsHtml = '<p class="small"><i class="fas fa-cogs me-1"></i>Action summary:</p>';
        
        // Create a more compact display for tool calls
        toolCalls.forEach(tool => {
            let args;
            try {
                // Format JSON more compactly
                args = JSON.parse(tool.arguments);
                
                // Create simplified version for display
                const simplifiedArgs = {};
                for (const key in args) {
                    // Truncate long string values
                    if (typeof args[key] === 'string' && args[key].length > 60) {
                        simplifiedArgs[key] = args[key].substring(0, 57) + '...';
                    } else {
                        simplifiedArgs[key] = args[key];
                    }
                }
                
                args = JSON.stringify(simplifiedArgs, null, 1);
            } catch (e) {
                // If not valid JSON, use as is
                args = tool.arguments;
            }
            
            // Simplified tool call display
            toolCallsHtml += `
                <div class="tool-call">
                    <div class="tool-call-header">
                        <span class="tool-name">${escapeHtml(tool.name)}</span>
                    </div>
                    <div class="tool-args"><pre>${escapeHtml(args)}</pre></div>
                </div>
            `;
        });
        
        toolCallsContent.innerHTML = toolCallsHtml;
        toolCallsDiv.appendChild(toolCallsContent);
        conversationContainer.appendChild(toolCallsDiv);
        
        // Scroll to the bottom
        conversationContainer.scrollTop = conversationContainer.scrollHeight;
    }
    
    // Helper function to escape HTML
    function escapeHtml(unsafe) {
        return unsafe
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }
    
    // Add initial welcome message
    if (conversationContainer.querySelectorAll('.message').length === 0) {
        addMessage('system', 'Welcome to the AI Agent of Profit! Ask me about my wallet, token positions, market data, or any DeFi operations I can perform.');
    }
    
    // Function to toggle sidebar visibility
    function toggleSidebar() {
        document.body.classList.toggle('sidebar-hidden');
        sidebarToggle.classList.toggle('active');
        
        // Save preference to localStorage
        const isHidden = document.body.classList.contains('sidebar-hidden');
        localStorage.setItem('sidebar-hidden', isHidden);
    }
    
    // Function to initialize sidebar state based on saved preference and screen size
    function initializeSidebarState() {
        const savedState = localStorage.getItem('sidebar-hidden');
        
        // On mobile, default to hidden sidebar
        if (window.innerWidth < 992) {
            document.body.classList.add('sidebar-hidden');
            sidebarToggle.classList.remove('active');
        } 
        // On desktop, use saved preference or default to visible
        else if (savedState === 'true') {
            document.body.classList.add('sidebar-hidden');
            sidebarToggle.classList.remove('active');
        } else {
            document.body.classList.remove('sidebar-hidden');
            sidebarToggle.classList.add('active');
        }
    }
    
    // Handle window resize
    window.addEventListener('resize', function() {
        // Responsive behavior adjustments if needed
        if (window.innerWidth >= 992 && !document.body.classList.contains('sidebar-hidden')) {
            sidebarToggle.classList.add('active');
        }
    });
});
