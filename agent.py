from langchain_anthropic import ChatAnthropic
from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated, List

llm = ChatAnthropic(model="claude-3-haiku-20240307", max_tokens_to_sample=4000)

class Chapter(TypedDict):
    number: int
    content: str


def update_chapters(left, right):
    # coerce to list
    if not isinstance(left, list):
        left = [left]
    if not isinstance(right, list):
        right = [right]
    if len(right) != 1:
        raise ValueError
    chapter = right[0]
    merged = left.copy()
    if left[-1]['number'] == chapter['number']:
        merged[-1] = chapter
    else:
        merged.append(chapter)
    return merged

class State(TypedDict):
    # User's initial inputs (could be updated later)
    summary: str
    details: str
    style: str
    chapters: Annotated[List[Chapter], update_chapters]
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
Review the novel concept, details, and previously written chapters. Brainstorm ideas for plot, character development, symbols, allusion, and themes. Create a rough outline of the major events and scenes. Make notes on the chapter's beginning, middle, and end
</brainstorm>
<content>
Write a full, final draft of the chapter (2000-5000 words). Follow the outline and notes, maintaining the desired style and details. Focus on engaging storytelling, vivid descriptions, and realistic dialogue
</content>
</Chapter>

The keys to success are:
- Communicate clearly and work collaboratively with the user. Be well-attuned to their preferences and vision
- Be organized and keep the novel's structure and plan in mind
- Incorporate feedback graciously while preserving story integrity 
- Pay attention to detail in writing, revising and proofreading
Always respond using the 'Chapter' function and then immediately stop."""

edit_prompt = """Here's what we have so far:

<Progress>
{chapters_str}
</Progress>

Here was a draft of the new chapter:

<Draft>
{draft}
</Draft>

Here is some edits we want to make to that chapter:

<EditInstructions>
{edit}
</EditInstructions>

Rewrite the the chapter with those instructions in mind. Reminder to respond in the correct <Chapter> form."""

continue_prompt = """Here's what we have so far:

<Progress>
{chapters_str}
</Progress>

Write the next chapter, keeping the following instructions in mind

<Instructions>
{instructions}
</Instructions>

Write the next chapter with those instructions in mind.
This chapter should pick up seamlessly from the previous chapters.
It should be a logical follow up.
Reminder to respond in the correct <Chapter> form."""

def parse(txt: str):
    if "<content>" in txt:
        txt = txt.split("<content>")[1]
    if "</content>" in txt:
        txt = txt.split("</content>")[0]
    return txt

def write_first_chapter(state):
    prompt = instructions.format(summary=state['summary'], details=state['details'], style=state['style'])
    response = llm.invoke(prompt)
    chapter = parse(response.content)
    return {"chapters": [{"number": 0, "content": chapter}], "rewrite_instructions": "", "continue_instructions": ""}


def edit_chapter(state):
    chapters_str = "\n\n".join(
        [f"Chapter {c['number']}\n\n{c['content']}" for c in state['chapters'][:-1]]
    ).strip()
    user_message = edit_prompt.format(
        chapters_str=chapters_str, 
        draft=state['chapters'][-1]['content'], 
        edit=state['rewrite_instructions']
    )
    prompt = instructions.format(summary=state['summary'], details=state['details'], style=state['style'])
    response = llm.invoke([{"role": "system", "content": prompt}, {"role": "user", "content": user_message}])
    chapter = parse(response.content)
    return {"chapters": [{"number": state['chapters'][-1]['number'], "content": chapter}], "rewrite_instructions": "", "continue_instructions": ""}


def continue_chapter(state):
    chapters_str = "\n\n".join(
        [f"Chapter {c['number']}\n\n{c['content']}" for c in state['chapters']]
    ).strip()
    user_message = continue_prompt.format(
        chapters_str=chapters_str, 
        instructions=state['continue_instructions']
    )
    prompt = instructions.format(summary=state['summary'], details=state['details'], style=state['style'])
    response = llm.invoke([{"role": "system", "content": prompt}, {"role": "user", "content": user_message}])
    chapter = parse(response.content)
    return {"chapters": [{"number": state['chapters'][-1]['number'] + 1, "content": chapter}], "rewrite_instructions": "", "continue_instructions": ""}

def router(state):
    if len(state.get('chapters', [])) == 0:
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