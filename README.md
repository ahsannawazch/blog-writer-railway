# Content Writer Application

This project is a content generation and interaction system designed to assist users in creating and editing content efficiently. It leverages advanced AI models and tools to classify user intent, analyze topics, generate questions, perform web searches, and create drafts. Additionally, it includes a conversational feature with memory capabilities.

## Features

- **Intent Classification**: Identifies the user's intent based on their input.
- **Topic Analysis**: Analyzes the topic provided by the user.
- **Question Generation**: Generates structured questions related to the analyzed topic.
- **Web Search**: Searches the web for answers to the generated questions.
- **Content Writing**: Creates an initial draft based on the user's query and relevant Q&A pairs.
- **Content Editing**: Enhances or modifies the generated content based on user instructions.
- **ChitChat**: Engages in conversational interactions with memory support.

## Technologies Used

- **Python**: Core programming language.
- **Chainlit**: For managing user interactions.
- **Pydantic AI**: For AI model integration.
- **LangGraph**: For building and managing state graphs.
- **Tavily**: For web search functionality.
- **Mem0**: For memory management.
- **LangSmith**: For tracing and debugging.

## Setup Instructions

1. Clone the repository.
2. Install the required dependencies using:
   ```bash
   pip install -r requirements.txt
   ```
3. Set up environment variables by creating a `.env` file and adding the necessary configurations.
4. Run the application using:
   ```bash
   python app.py
   ```

## How It Works

1. **User Input**: The user provides a query or instruction.
2. **Graph Execution**: The system processes the input through a state graph with nodes for intent classification, topic analysis, question generation, web search, content writing, and editing.
3. **Output**: The final content or response is generated and displayed to the user.

## File Structure

- `app.py`: Main application file containing the logic and state graph.
- `prompts.py`: Contains prompts used by the AI models.
- `requirements.txt`: Lists the dependencies required for the project.
- `Dockerfile`: Configuration for containerizing the application.

## Contributing

Contributions are welcome! Please fork the repository and submit a pull request with your changes.

## License

This project is licensed under the MIT License. See the LICENSE file for details.