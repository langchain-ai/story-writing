from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated, List, Dict
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from copy import deepcopy

title_llm = ChatOpenAI(model="gpt-4o",metadata={"name":"title_llm"})
chapter_title_llm = ChatOpenAI(model="gpt-4o",metadata={"name":"chapter_title_llm"})
summary_llm = ChatOpenAI(model="gpt-4o",metadata={"name":"summary_llm"})
brainstorm_llm = ChatOpenAI(model="gpt-4o",temperature=1,metadata={"name":"brainstorm_llm"})
plan_llm = ChatAnthropic(model="claude-3-haiku-20240307",metadata={"name":"plan_llm"})
write_llm = ChatAnthropic(model="claude-3-sonnet-20240229",metadata={"name":"write_llm"})

summary_messages = [
    ("system", "You are an assistant solely focused on summarizing books. Your goal \
     is to summarize so that all logical dependencies are captured. It is not important for \
     you to summarize minute details but rather focus on important things like character names, \
     relationships, and the sequence of events that have occured so far. Your summary should contain enough \
     information for a human to read it and reconstruct the book's main plotline accurately."),
    ("human", "Please help me summarize the following book: {chapters_str}"),
]

brainstorm_messages = [
    ("system", "You are an assistant tasked with brainstorming ideas for brainstorming ideas for \
    a chapter in a story. You should brainstorm ideas relevant to the plotline and in accordance with \
     the users wishes for the next chapter. You should brainstorm multiple ideas for what the chapter could \
     be about, making detailed descriptions of all your ideas. Do not return anything other than a numbered list of ideas."),
     ("human", "{summary_request}"),
     ("human", "{detail_request}"),
     ("human", "{style_request}"),
     ("human", "This is the summary of the story up to this point: {story_summary}"),
     ("human", "I would like to {action}. Can you please help me brainstorm ideas for that?")
]

outline_messages = [
    ("system", "You are an assistant tasked with outlining a new chapter in a story. You will be provided with \
     some potential ideas for the chapter. You should choose one of those ideas, and then write a clear outline \
     for it. Your outline should include a beginning, middle, and end. You should only return the outline of the \
     story, not any other information or text. Here is an example of what you should return: \
     \
     I. Introduction\n- **Setting Description:**\n  - The old mansion at the end of Hawthorn Lane, shrouded in mystery and ivy.\n  - Historical significance: Passed down through generations in Emma's family.\n- **Character Introduction:**\n  - Emma, 27 years old, determined to uncover family secrets.\n  - Mention of the secret room rumored by her great-grandmother.\n\n#### II. Emma's Curiosity and Determination\n- **Great-Grandmother's Mention:**\n  - Flashback to Emma's childhood memory of great-grandmother hinting at the secret room.\n- **Emma's Motivation:**\n  - Transition from childhood curiosity to adult determination to uncover the secret.\n\n#### III. The Stormy Evening\n- **Setting the Scene:**\n  - Description of the stormy evening: rain, wind, ancient trees.\n- **Preparation:**\n  - Emma armed with a flashlight and an old blueprint found in the attic.\n  - Description of the blueprint: yellowed, frayed, delicate.\n\n#### IV. Discovery of the Unmarked Space\n- **Blueprint Examination:**\n  - Emma tracing the lines and discovering the unmarked space between the library and the drawing-room.\n- **Realization:**\n  - Heart skipping a beat; determination to investigate further.\n\n#### V. The Library\n- **Description of the Library:**\n  - Cavernous room, floor-to-ceiling bookshelves, scent of aged paper.\n- **Search for Irregularities:**\n  - Emma scanning the walls, finding the worn bookshelf.\n- **The Lost Histories Book:**\n  - Discovery of the out-of-place leather-bound volume.\n  - Pulling the book to reveal the secret passage.\n\n#### VI. The Hidden Passage\n- **Bookshelf Mechanism:**\n  - Bookshelf swinging open to reveal a narrow passage.\n- **Initial Hesitation:**\n  - Emma’s breath catching, moment of hesitation.\n- **Descent:**\n  - Flashlight beam, steep spiral staircase, mix of fear and excitement.\n\n#### VII. The Secret Room\n- **Room Description:**\n  - Small, dimly lit, musty air.\n- **The Wooden Chest:**\n  - Intricately carved surface, Emma’s trembling fingers lifting the lid.\n- **Contents of the Chest:**\n  - Faded photographs, letters tied with ribbon, ornate key.\n\n#### VIII. Discoveries and Revelations\n- **Photographs:**\n  - Black-and-white image of great-grandmother and an unknown man.\n  - Noting the secret happiness in their eyes.\n- **Love Letters:**\n  - Untying the ribbon, reading the first letter.\n  - Story of forbidden love and a promise to protect their secret.\n\n#### IX. Emotional Connection\n- **Emma’s Reaction:**\n  - Eyes filling with tears, realization of the room’s significance.\n- **Legacy of Love:**\n  - Understanding the room as a sanctuary of love and resilience.\n- **The Ornate Key:**\n  - Speculation about what the key might unlock.\n\n#### X. Emma's Resolution\n- **Vow to Uncover the Full Story:**\n  - Determination to piece together the past.\n  - Honoring the legacy of love and courage.\n- **Emerging from the Secret Room:**\n  - Returning up the spiral staircase, storm waning, dawn breaking.\n\n#### XI. Conclusion\n- **Newfound Connection:**\n  - Deeper connection to heritage.\n  - Understanding the importance of discovering, cherishing, and passing on family secrets.\n- **End of a Mystery:**\n  - Mansion holds one less mystery.\n  - Walls whispering a new story of love and resilience.\n\n### Themes and Motifs\n- **Heritage and Legacy:**\n  - Importance of family history and secrets.\n- **Love and Resilience:**\n  - Enduring nature of love and strength across generations.\n- **Curiosity and Discovery:**\n  - Emma's journey from curiosity to discovery and understanding.\n  \n### Literary Devices\n- **Imagery:**\n  - Vivid descriptions of the mansion, storm, and secret room.\n- **Foreshadowing:**\n  - Hints from great-grandmother about the secret room.\n- **Symbolism:**\n  - The ornate key symbolizing unlocking the past and hidden truths."),
     ("human", "{summary_request}"),
     ("human", "{detail_request}"),
     ("human", "{style_request}"),
     ("human", "This is the summary of the story up to this point: {story_summary}"),
     ("human", "Here are a list of ideas for the chapter I would like you to outline: {brainstorm_ideas}"),
     ("human", "I would like to {action}. Can you please make a clear outline for that chapter?")
]

write_messages = [
    ("system", "You are an assistant tasked with writing book chapters. You will receive an outline \
     of the chapter and you should return the content of the chapter only. Do not return the chapter numnber, the chapter title, or any other information \
     related to the chapter. Just write the words that would appear on the page. You should \
     return the content like the following example: \
     \
     \
     The old mansion stood at the end of Hawthorn Lane, shrouded in mystery and ivy. It had been in Emma\'s family for generations, passed down from one enigmatic ancestor to another. Though the house had always been a source of curiosity, none of the family\'s secrets intrigued Emma quite as much as the rumored secret room.\n\nHer great-grandmother had once mentioned it in passing, her eyes twinkling with a mixture of mischief and nostalgia. But Emma had been too young to press for details then. Now, at twenty-seven, her curiosity had matured into a determination.\n\nIt was a stormy evening when Emma decided to search for the room. The rain battered against the windows, and the wind howled through the ancient trees surrounding the mansion. Armed with a flashlight and an old, dusty blueprint of the house she found in the attic, she made her way through the labyrinthine corridors.\n\nThe blueprint had been yellowed with age, its edges frayed and delicate. Emma traced her finger along the lines, noting the familiar rooms and passages. Her heart skipped a beat when she noticed a small, unmarked space between the library and the drawing-room—an area that didn’t correspond with any door or window she knew of.\n\nShe hurried to the library, her footsteps echoing in the vast, empty halls. The library was a cavernous room, filled with floor-to-ceiling bookshelves and the comforting scent of aged paper. She scanned the walls, searching for any irregularities. Her eyes landed on a particular bookshelf, slightly more worn than the others, its wood darker and dustier.\n\nEmma approached it cautiously, running her fingers along the spines of the old books. One of the books, a leather-bound volume titled \"The Lost Histories,\" seemed oddly out of place. She pulled it, and with a soft click, the entire bookshelf swung open to reveal a narrow passage.\n\nHer breath caught in her throat. The flashlight beam sliced through the darkness, revealing a steep, spiral staircase. She hesitated only for a moment before descending, her heart pounding with a mix of fear and excitement.\n\nThe staircase led to a small, dimly lit room. The air was musty, filled with the scent of forgotten memories. In the center of the room stood a wooden chest, its surface intricately carved with symbols Emma didn\'t recognize. She knelt beside it, her fingers trembling as she lifted the lid.\n\nInside the chest were relics of the past: faded photographs, letters tied with ribbon, and a peculiar, ornate key. Emma picked up one of the photographs. It was a black-and-white image of her great-grandmother as a young woman, standing beside a man Emma had never seen before. They were smiling, their eyes filled with a secret happiness.\n\nShe turned her attention to the letters, carefully untying the ribbon. The delicate parchment crackled as she unfolded the first one. It was a love letter, written in elegant, flowing script. As she read, a story unfolded—a tale of forbidden love, hidden meetings, and a promise to protect their secret at all costs.\n\nEmma\'s eyes filled with tears. The secret room was more than just a hidden space; it was a sanctuary of love, a testament to the resilience of her great-grandmother\'s spirit. The ornate key, she realized, must unlock something even more precious.\n\nWith newfound determination, Emma vowed to uncover the full story. She would piece together the fragments of the past, honoring the legacy of love and courage that had been hidden away for so long.\n\nAs she made her way back up the spiral staircase, the storm outside began to wane, the first rays of dawn breaking through the clouds. The secret room had given her more than just answers; it had bestowed upon her a deeper connection to her heritage, a reminder that some secrets are meant to be discovered, cherished, and passed on.\n\nAnd thus, the old mansion at the end of Hawthorn Lane held one less mystery, but its walls whispered a new story—a story of love, hidden away but never forgotten. \
    \
    Please remember to always only return the chapter writing itself. Do not return any other text."),
     ("human", "{summary_request}"),
     ("human", "{detail_request}"),
     ("human", "{style_request}"),
     ("human", "This is the summary of the story up to this point: {story_summary}"),
     ("human", "Here is the outline I would like you to follow when writing the chapter: {outline}"),
     ("human", "I would like to {action}. Can you please write the chapter for me, remebering to follow the outline I just provided? Pleease remember to return the chapter text only, not any commentary to the user or additional text.")
]

summary_prompt = ChatPromptTemplate.from_messages(summary_messages)
brainstorm_prompt = ChatPromptTemplate.from_messages(brainstorm_messages)
outline_prompt = ChatPromptTemplate.from_messages(outline_messages)
write_prompt = ChatPromptTemplate.from_messages(write_messages)

summary_chain = summary_prompt | summary_llm | StrOutputParser()
brainstorm_chain = brainstorm_prompt | brainstorm_llm | StrOutputParser()
outline_chain = outline_prompt | plan_llm | StrOutputParser()
write_chain = write_prompt | write_llm | StrOutputParser()

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

def write_chapter(user_message, chapters_summary, state):
    brainstorm_ideas = brainstorm_chain.invoke({'story_summary':chapters_summary,'action':user_message,'summary_request':state['summary_request'], \
                                                'detail_request':state['detail_request'],'style_request':state['style_request']})
    outline = outline_chain.invoke({'story_summary':chapters_summary,'action':user_message,'summary_request':state['summary_request'], \
                                                'detail_request':state['detail_request'],'style_request':state['style_request'],'brainstorm_ideas':brainstorm_ideas})

    response = write_chain.invoke({'story_summary':chapters_summary,'action':user_message,'summary_request':state['summary_request'], \
                                                'detail_request':state['detail_request'],'style_request':state['style_request'],'outline':outline})
    chapter_content = response
    chapter_title = chapter_title_llm.invoke(f"Please come up with a title for the following chapter: {chapter_content}. The title should be 6 words or less.").content.replace("\"","")
    return chapter_content, chapter_title

def get_title(state,first_chapter):
    return title_llm.invoke(f"Please come up with a short title, less than 6 words, for a story. The story has the following overall plot {state['summary']}, and here is the first chapter {first_chapter}").content.replace("\"","")

def write_first_chapter(state):
    if state['summary']:
        state['summary_request'] = f"I would like the overall plot of the story to be {state['summary']}"
    
    if state['details']:
        state['detail_request'] = f"I would like you to keep the following details in mind when writing {state['details']}"
    
    if state['style']:
        state['style_request'] = f"Please make sure to use the following writing style {state['style']}"
    chapter_content, chapter_title = write_chapter("Please write the first chapter of this story.", "no story up to this point, this is the first chapter!", state)

    
    state['current_chapter_id'] = '1'
    state['chapter_id_viewing'] = '1'
    state['chapter_graph'] = {'1':Chapter(content=chapter_content,title=chapter_title,children=[],siblings=[],cousins=[],parent='-1')}
    state['story_title'] = get_title(state,chapter_content)
    return state

edit_prompt = """Here is the current state of the new chapter:

<Draft>
{draft}
</Draft>

Here are some edits I want to make to that chapter:

<EditInstructions>
{edit}
</EditInstructions>"""

def edit_chapter(state):
    chapters_summary = summarize_current_story(state,state['chapter_graph'][state["chapter_id_viewing"]]['parent'])
    user_message = edit_prompt.format(
        chapters_summary=chapters_summary, 
        draft=state['chapter_graph'][state['chapter_id_viewing']]['content'], 
        edit=state['rewrite_instructions']
    )

    chapter_content, chapter_title = write_chapter(user_message, chapters_summary, state)
    
    #create new chapter
    state['chapter_graph'][str(int(state["current_chapter_id"])+1)] = Chapter(content=chapter_content,title=chapter_title,children=[], \
                siblings=deepcopy(state["chapter_graph"][state["chapter_id_viewing"]]['siblings']+[state["chapter_id_viewing"]]), \
                cousins=deepcopy(state["chapter_graph"][state["chapter_id_viewing"]]['cousins']), \
                parent=deepcopy(state["chapter_graph"][state["chapter_id_viewing"]]['parent']))
    #update siblings
    for sibling in state["chapter_graph"][str(int(state["chapter_id_viewing"]+1))]['siblings']:
        state["chapter_graph"][sibling]['siblings'].append(str(int(state["current_chapter_id"])+1))

    state["chapter_graph"][state["chapter_id_viewing"]]['siblings'].append(str(int(state["current_chapter_id"])+1))
    state["current_chapter_id"] = str(int(state["current_chapter_id"])+1)
    state["chapter_id_viewing"] = deepcopy(state["current_chapter_id"])
    return state

continue_prompt = """Here is what I want in the next chapter:

<Instructions>
{instructions}
</Instructions>"""

def continue_chapter(state):
    chapters_summary = summarize_current_story(state,state["chapter_id_viewing"])
    user_message = continue_prompt.format(
        chapters_summary=chapters_summary, 
        instructions=state['continue_instructions']
    )
    
    chapter_content, chapter_title = write_chapter(user_message, chapters_summary, state)
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

# State Definitions
class Chapter(TypedDict):
    content: str
    """Content of the chapter"""
    title: str
    """Title of the chapter"""
    children: list
    """Direct descendants of the chapter - chapters you get by clicking Continue"""
    siblings: list
    """Direct edit descendants of the chapter - chapters you get by clicking Edit"""
    cousins: list
    """Chapters that originated from the same parent but are not directly related"""
    parent: int
    """For chapter number n, it is the node of chapter number n-1 that is directly related"""
    
def update_chapter_graph(old_chapter_graph, new_chapter_graph):
    # Always add nodes to the overall graph
    if isinstance(new_chapter_graph,dict):
        old_chapter_graph.update(new_chapter_graph)
        return old_chapter_graph

class State(TypedDict):
    summary: str
    """Summary user passes in at beginning of story"""
    details: str
    """Details provided by user at beginning of story"""
    style: str
    """Desired writing style from the user"""
    summary_request: str = ""
    """Prompt engineered summary instructions for LLM"""
    detail_request: str = ""
    """Prompt engineered detial instructions for LLM"""
    style_request: str = ""
    """Prompt engineered writing style instructions for LLM"""
    chapter_graph: Annotated[dict[str, Chapter], update_chapter_graph]
    """Graph containing all of our chapter"""
    chapter_id_viewing: str
    """What node in the graph the user is currently viewing"""
    current_chapter_id: str
    """What is the current highest node (i.e. how many chapters have been written so far)"""
    rewrite_instructions: str
    """Instructions to edit a chapter from the user"""
    continue_instructions: str
    """Instructions to write the next chapter from the suer"""
    story_title: str = ""
    """Overall title of the story"""

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