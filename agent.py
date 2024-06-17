from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated, List, Dict
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from copy import deepcopy

'''
llm = ChatAnthropic(model="claude-3-haiku-20240307", max_tokens_to_sample=4000)
summary_llm = ChatAnthropic(model="claude-3-sonnet-20240229")
'''
llm = ChatOpenAI(model="gpt-4o")
summary_llm = ChatOpenAI(model="gpt-4o")

messages = [
    ("system", "You are an assistant solely focused on summarizing books. Your goal \
     is to summarize so that all logical dependencies are captured. It is not important for \
     you to summarize minute details but rather focus on important things like character names, \
     relationships, and the sequence of events that have occured so far. Your summary should contain enough \
     information for a human to read it and reconstruct the book's main plotline accurately."),
    ("human", "Please help me summarize the following book: {chapters_str}"),
]

prompt = ChatPromptTemplate.from_messages(messages)

summary_chain = prompt | summary_llm | StrOutputParser()

class Chapter(TypedDict):
    content: str
    title: str
    children: list
    siblings: list
    cousins: list
    parent: int
    
def update_chapter_graph(old_chapter_graph, new_chapter_graph):
    if isinstance(new_chapter_graph,dict):
        old_chapter_graph.update(new_chapter_graph)
        return old_chapter_graph

class State(TypedDict):
    # User's initial inputs (could be updated later)
    summary: str
    details: str
    style: str
    chapter_graph: Annotated[dict[str, Chapter], update_chapter_graph]
    chapter_id_viewing: str
    current_chapter_id: str
    rewrite_instructions: str
    continue_instructions: str

instructions = """Your task is to collaborate with the user to write a novel, chapter by chapter, using the following process:

First, gather the initial information from the user:

<init>
Novel concept summary: {summary}
Additional details to include: {details}
Preferred writing style: {style}
</init>

Then, for each chapter:

<Chapter>
<brainstorm>
Review the novel concept, details, and previously written chapters. Brainstorm multiple ideas for plot, character development, symbols, allusion, and themes. Create a rough outline of the major events and scenes. Make notes on the chapter's beginning, middle, and end. Make multiple ideas for each part of the chapter.
</brainstorm>
<filtering>
Filter the brainstorm, only using the ideas that fit logically in the plot and follow the users instructions fairly rigidly.
</filtering>
<content>
Write a full, final draft of the chapter (2000-5000 words). Follow the outline and notes, maintaining the desired style and details. Focus on engaging storytelling, vivid descriptions, and realistic dialogue. Make sure there are no logical inconsitencies in the story as well. Do not include any of the brainstorm or the title of the chapter in the content, just the actual content of the chapter.
</content>
<chaptertitle>
Based on the final draft of the chapter, select a short chapter title that fits well. Plase don't include newline characters in the chapter title.
</chaptertitle>
</Chapter>

The keys to success are:
- Communicate clearly and work collaboratively with the user. Be well-attuned to their preferences and vision.
- Be organized and keep the novel's concept summary in mind, do not deviate too far from the summary and other prompts the user enters.
- Incorporate feedback graciously while preserving story integrity.
- Try to use the writig style and sound as similar to it as you can.
- Pay attention to detail in writing, revising and proofreading, make sure it reads like a novel not a blog post or short story.
- Keep the formatting strict, write the chapter content inbetween <content> </content> tags, and write the chapter title in between <chaptertitle> </chaptertitle> tags. Do not write the chapter title at the start of the the <content> </content> tags.
Always respond using the 'Chapter' function and then immediately stop. Do not respond by saying something along the lines of: I understand the task and am ready to help. Always return a written chapter, following the <Chapter> function instructions."""

edit_prompt = """Here's what we have so far:

<Progress>
{chapters_summary}
</Progress>

Here is the current state of the new chapter:

<Draft>
{draft}
</Draft>

Here are some edits we want to make to that chapter:

<EditInstructions>
{edit}
</EditInstructions>

Rewrite the the chapter with those instructions in mind. Reminder to respond in the correct <Chapter> form.
That means writing both <content> and a new <chaptertitle>. Please make sure to only return text that is in the story, not any comments you have to the user.
Ensure that any edits do not detract from the overall plot of the chapter unless you were specifically instructed to do so by the user."""

continue_prompt = """Here's what we have so far:

<Progress>
{chapters_summary}
</Progress>

Write the next chapter in this story, keeping the following instructions in mind

<Instructions>
{instructions}
</Instructions>

Write the next chapter with those instructions in mind.
This chapter should pick up seamlessly from the previous chapters.
It should be a logical follow up.
Reminder to respond in the correct <Chapter> form."""

def parse(txt: str):
    chapter_txt = txt
    if "<content>" in txt and "</content>" in txt:
        chapter_txt = txt.split("<content>")[1]
        chapter_txt = chapter_txt.split("</content>")[0]
    title = ""
    if "<chaptertitle>" in txt and "</chaptertitle>" in txt:
        title = txt.split("<chaptertitle>")[1]
        title = title.split("</chaptertitle>")[0]
    return chapter_txt, title

def write_first_chapter(state):
    prompt = instructions.format(summary=state['summary'], details=state['details'], style=state['style'])
    response = llm.invoke(prompt)
    chapter_content, chapter_title = parse(response.content)

    state['current_chapter_id'] = '1'
    state['chapter_id_viewing'] = '1'
    state['chapter_graph'] = {'1':Chapter(content=chapter_content,title=chapter_title,children=[],siblings=[],cousins=[],parent='-1')}
    return state

def summarize_current_story(state,chapter_id):
    if chapter_id == '-1':
        return ""
    current_chapter_id = chapter_id
    chapters_currently_selected_text = [state['chapter_graph'][current_chapter_id]['content']]
    while state['chapter_graph'][current_chapter_id]['parent'] != '-1':
        chapters_currently_selected_text.append(state['chapter_graph'][current_chapter_id]['content'])
        current_chapter_id = state['chapter_graph'][current_chapter_id]['parent']
    chapters_str = "\n\n".join(
        [f"Chapter {i}\n\n{chapters_currently_selected_text[i]}" for i in range(len(chapters_currently_selected_text))]
    ).strip()
    return summary_chain.invoke({"chapters_str": chapters_str})

def edit_chapter(state):
    chapters_summary = summarize_current_story(state,state['chapter_graph'][state["chapter_id_viewing"]]['parent'])
    user_message = edit_prompt.format(
        chapters_summary=chapters_summary, 
        draft=state['chapter_graph'][state['chapter_id_viewing']]['content'], 
        edit=state['rewrite_instructions']
    )
    prompt = instructions.format(summary=state['summary'], details=state['details'], style=state['style'])
    response = llm.invoke([{"role": "system", "content": prompt}, {"role": "user", "content": user_message}])
    chapter_content, chapter_title = parse(response.content)
    
    #create new chapter
    state['chapter_graph'][str(int(state["current_chapter_id"])+1)] = Chapter(content=chapter_content,title=chapter_title,children=[], \
                                                   siblings=deepcopy(state["chapter_graph"][state["chapter_id_viewing"]]['siblings']+[state["chapter_id_viewing"]]), \
                                                   cousins=deepcopy(state["chapter_graph"][state["chapter_id_viewing"]]['children']), \
                                                   parent=deepcopy(state["chapter_graph"][state["chapter_id_viewing"]]['parent']))
    #update siblings
    for sibling in state["chapter_graph"][state["chapter_id_viewing"]]['siblings']:
        state["chapter_graph"][sibling]['siblings'].append(str(int(state["current_chapter_id"])+1))

    state["chapter_graph"][state["chapter_id_viewing"]]['siblings'].append(str(int(state["current_chapter_id"])+1))
    state["current_chapter_id"] = str(int(state["current_chapter_id"])+1)
    state["chapter_id_viewing"] = deepcopy(state["current_chapter_id"])
    return state


def continue_chapter(state):
    chapters_summary = summarize_current_story(state,state["chapter_id_viewing"])
    user_message = continue_prompt.format(
        chapters_summary=chapters_summary, 
        instructions=state['continue_instructions']
    )
    prompt = instructions.format(summary=state['summary'], details=state['details'], style=state['style'])
    response = llm.invoke([{"role": "system", "content": prompt}, {"role": "user", "content": user_message}])
    chapter_content, chapter_title = parse(response.content)

    #create new chapter
    state['chapter_graph'][str(int(state["current_chapter_id"])+1)] = Chapter(content=chapter_content,title=chapter_title,children=[],siblings=[], \
                                                   cousins=deepcopy(state["chapter_graph"][state["chapter_id_viewing"]]['children']),\
                                                    parent=deepcopy(state['chapter_id_viewing']))
    #update cousins
    for child in state["chapter_graph"][state["chapter_id_viewing"]]['children']:
        state["chapter_graph"][child]['cousins'].append(str(int(state["current_chapter_id"])+1))
    #update children
    state["chapter_graph"][state["chapter_id_viewing"]]['children'].append(str(int(state["current_chapter_id"])+1))
    state["current_chapter_id"] = str(int(state["current_chapter_id"])+1)
    state["chapter_id_viewing"] = deepcopy(state["current_chapter_id"])
    return state


def router(state):
    if len(state.get('chapter_graph', [])) == 0:
        return "first"
    elif state.get('rewrite_instructions', ''):
        return "rewrite"
    else:
        return "continue"


graph = StateGraph(State)
graph.set_conditional_entry_point(router)
graph.add_node("first", write_first_chapter)
graph.add_node("rewrite", edit_chapter)
graph.add_node("continue", continue_chapter)
graph.add_edge("first", END)
graph.add_edge("rewrite", END)
graph.add_edge("continue", END)
graph = graph.compile()