import chainlit as cl
from pydantic_ai import Agent
from pydantic import BaseModel
from pydantic_ai.models.groq import GroqModel
from prompts import topic_analyst_prompt_v2, get_list_prompt, writer_prompt_v2, intent_classifier_prompt, editor_prompt
import os
from typing import Annotated, List, Dict
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.types import Send
from tavily import TavilyClient
from langchain_core.tracers.context import tracing_v2_enabled
from langgraph.checkpoint.memory import MemorySaver

from mem0 import MemoryClient
mem0 = MemoryClient()

from dotenv import load_dotenv
load_dotenv()

# LangSmith Configuration
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_PROJECT"] = "content-writer"

llama_model = GroqModel(model_name="llama-3.1-8b-instant")
gemma_model = GroqModel(model_name="gemma2-9b-it")
llama_4_model = GroqModel(model_name="meta-llama/llama-4-scout-17b-16e-instruct")

class State(TypedDict):
    query: str
    intention: str
    topic_analyzer: str
    questions_list: list
    web_search_result: Annotated[list, add_messages]  
    initial_draft: str
    editor_draft: Dict[str, str]
    status: str
    ChitChat_history: Annotated[list, add_messages]
    user_id: str
    # agent_id: str
    # run_id: str

class QueriesState(TypedDict):
    question: str

graph_builder = StateGraph(State)

# Intent Classifier Node
def intent_classifier(state: State):
    print(f'________________Getting to know the user intention____')
    user_prompt = state['query']
    agent = Agent(
        model= llama_model,
        retries=3,
        system_prompt=intent_classifier_prompt,
        instrument=False
    )
    response = agent.run_sync(user_prompt=user_prompt)
    print(f'User Intention: {response.output}')
    return {'intention': response.output}


# Topic Analyzer Node
def topic_analyzer(state: State):
    print(f'________________Entering into Topic Analyser Node____')
    agent = Agent(
        model=llama_model,
        system_prompt=topic_analyst_prompt_v2,
        retries=3,
    )
    user_prompt = state['query']
    response = agent.run_sync(user_prompt=user_prompt)
    print(f'_____________Exiting into Topic Analyser Node______')
    return {"topic_analyzer": response.output}

# Question List Generator
def list_questions(state: State):
    class QuestionList(BaseModel):
        questions: List[str]  
    print("___________Getting structured Questions________")
    list_agent = Agent(
        model=gemma_model,
        output_type=QuestionList,
        system_prompt=get_list_prompt,
    )
    unstructured_questions = state['topic_analyzer']
    response = list_agent.run_sync(user_prompt=unstructured_questions)
    total_questions = len(response.output.questions)
    print(f"___I think, I got {total_questions}___")
    return {"questions_list": response.output.questions}

# web search node
def web_search(state: QueriesState):
    # print("[Chainlit] Entering web_search node")
    query = state['question']
    tavily_client = TavilyClient()
    response = tavily_client.search(
        query=query,
        search_depth="advanced",
        max_results=5,
        include_answer="advanced",
        include_images=False
    )
    search_result = response['answer']
    print(" Exiting web_search node")
    return {'web_search_result': [search_result]}

# question mapper
def map_questions_to_search(state: State):
    questions = state['questions_list']
    return [Send(node='web_search', arg=QueriesState(question=question)) for question in questions]

# writer node 
def writer_node(state: State):
    query = state['query']
    questions = state['questions_list']
    answers = state['web_search_result']
    QA_pairs = ""

    for question, answer in zip(questions, answers):
        QA_pairs += f"Question: {question}\nAnswer: {answer.content}\n\n"
    
    writer_agent = Agent(
        model=llama_4_model,
        retries=3,
        system_prompt=writer_prompt_v2,
    )
    prompt = f"""{query} \n\n Relevant Questions and Answers: {QA_pairs} """
    response = writer_agent.run_sync(user_prompt=prompt)
    
    # Save initial draft to mem0
    # mem0.add(response.output, metadata={"type": "blog_draft_initial"}, user_id=user_id)
    
    return {"initial_draft": response.output}

# Editor Node with mem0 memory
def editor_node(state: State):
    print("\n__________We are in editor node____________________\n")
    draft = None
    
    if state.get('editor_draft'):
        status = "Using the latest editor's draft for further enhancements.... "
        print(status)   
        draft = state['editor_draft']        

    elif state.get('initial_draft'):
        status = "Editing the Already Generated Blog:"
        print(status)
        draft = state['initial_draft']
    else:
        status = "Please generate a blog first. Can't edit an empty blog."
        print(status)

    if draft is not None:
        user_instruction = f"Instruction about editing: {state['query']} \n\n The Blog: {draft}"
        editor_agent = Agent(           
            model=llama_4_model,                
            system_prompt=editor_prompt,
            retries=3
        )   

        # prompt = f'Instruction: Change the tone of the Blog to Gen-z. Here is the blog: {initial_draft}'
        response = editor_agent.run_sync(user_prompt=user_instruction)
        
        print("_______________Exiting the EDITOR Node____________________")

        return {'editor_draft': response.output, 'status': status}    
    else:
        return {'editor_draft': 'No data to edit', 'status': status}
       
# ChitChat Node with memory
def ChitChat(state: State):
    query = state['query']
    user_id = state['user_id']
    print("Entering the chat node__________")
    
    # Retrieve relevant memories
    memories = mem0.search(query, limit=5, user_id=user_id, )   # test with app id/ run id/ agent id (for a session)
    context = "\n".join([messages["memory"] for messages in memories]) if memories else "No prior context."
    # print(f'Past Interactions so far: {context}')
    
    chat_agent = Agent(
        model=gemma_model,
        retries=3,
        system_prompt=f'You are a helpful assistant. Previous conversation:\n{context}\nRespond kindly.',
    )
    response = chat_agent.run_sync(user_prompt=query)
    # print(f'chat_response: {response.output}')
    
    # Store interaction in mem0
    mem0.add(f"User: {query}\nAssistant: {response.output}", metadata={"type": "chitchat"}, user_id=user_id)
    return {'ChitChat_history': response.output}

# Intent Router
def intent_router(state: State):                 
    intent = state['intention']
    if 'NewTopic' in intent:
        return 'topic_analyst'
    elif 'EditLastOutput' in intent:
        return 'Editor'
    else:
        return 'ChitChat'

# Graph Construction
def create_graph():
    # Nodes
    graph_builder.add_node('intent_classifier', intent_classifier)
    graph_builder.add_node('topic_analyst', topic_analyzer)
    graph_builder.add_node('list_questions', list_questions)
    graph_builder.add_node('web_search', web_search)
    graph_builder.add_node('writer_node', writer_node)
    graph_builder.add_node('Editor', editor_node)
    graph_builder.add_node('ChitChat', ChitChat)
    
    # Edges and conditionals
    graph_builder.add_edge(START,'intent_classifier')
    graph_builder.add_conditional_edges(
        'intent_classifier', intent_router, {
            'topic_analyst': 'topic_analyst',
            'Editor': 'Editor',
            'ChitChat': 'ChitChat'
        }
    )
    graph_builder.add_edge('topic_analyst','list_questions')
    graph_builder.add_conditional_edges('list_questions', map_questions_to_search, ['web_search'])
    graph_builder.add_edge('web_search', 'writer_node')
    graph_builder.add_edge('writer_node', END)
    graph_builder.add_edge('Editor', END)
    graph_builder.add_edge('ChitChat', END)
    
    memory = MemorySaver()
    return graph_builder.compile(checkpointer=memory)


        # # Optional: Set session/user ID for isolated memory
        # # mem0_user_id = "user_123"  # Replace with dynamic ID in production      (Later)
        
        # def ()
        # config = {"configurable": {"agent_id": "agent_47"}}           
        
        # initial_state = {"query": "Edit the blog: Can you make the introduction a bit more Gen -z ", "user_id": "ahsan8877", "agent_id": "agent_47"}
        # # initial_state = {"query": "Give me a blog: 'Does tesla have cigarette lighters?' ", "user_id": "ahsan8877", "agent_id": "agent_47"}
        

        # final_state = graph.invoke(initial_state, config=config)
        
        # for key, value in final_state.items():
        #     print(f"node: {key}\nData: {value}")
        #     print("__" * 40)
        # print(f"🔗 LangSmith Trace URL: {cb.get_run_url()}")

graph = create_graph()


# Testing new chainlit initiater
@cl.on_message
async def on_message(msg: cl.Message):
    user_query = msg.content
    # config = {"configurable": {"thread_id": cl.context.session.id}}
    config = {"configurable": {"thread_id": "1234"}}
    # print(config)

    with tracing_v2_enabled(project_name="content-writer") as cb:
        initial_state = {"query": user_query, "user_id": "ahsankhan"}

        final_nodes = ['writer_node', 'Editor', 'ChitChat']
        process_nodes = ['intent_classifier', 'topic_analyst', 'list_questions','web_search']
        all_nodes = ['intent_classifier', 'topic_analyst', 'list_questions', 'writer_node', 'Editor', 'ChitChat', 'web_search']

        for event in graph.stream(initial_state, config):
            for node in all_nodes:
                if node in event and node in process_nodes:
                    if node == "intent_classifier":
                        data = cl.Message(content="🤔 Thinking ... ") 
                        await data.send()
                    elif node == "topic_analyst":
                        data.content = "🔍 Understanding the User Request ..."
                        await data.update()
                    elif node == "list_questions":
                        data.content = "💡 Brainstorming the topic ..."
                        await data.update()
                    elif node == "web_search":
                        data.content = "🌐 Searching web ... It'll take a minute  "
                        await data.update()
                    
                # If node is in final nodes, send the output
                elif node in event and node in final_nodes:
                    if node == "writer_node":
                        data.content= "✅ Blog Generated!" 
                        await data.update()
 
                        writer_output = event[node]
                        if isinstance(writer_output, dict):
                            first_value = next(iter(writer_output.values()), None)
                            await cl.Message(content=str(first_value)).send()

                    elif node == "Editor":
                        editor_output = event[node]
                        data.content = f"✏️ {editor_output['status']}"
                        await data.update()
                        
                        if isinstance(editor_output, dict):
                            first_value = next(iter(editor_output.values()), None)
                            await cl.Message(content=str(first_value)).send()

                    elif node == "ChitChat":
                        data.content = "💬 Diving into Chat mode ... "
                        await data.update()
                        chat_output = event[node]

                        if isinstance(chat_output, dict):
                            first_value = next(iter(chat_output.values()), None)
                            await cl.Message(content=str(first_value)).send()
