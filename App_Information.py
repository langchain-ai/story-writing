import streamlit as st
from streamlit import runtime
from streamlit.runtime.scriptrunner import get_script_run_ctx
import asyncio
from streamlit_js_eval import streamlit_js_eval
import requests


async def main():
    st.markdown("""
    <style>
    /* Centering title horizontally */
    .centered-title {
        text-align: center;
    }
    </style>""",unsafe_allow_html=True)

    st.title("App Information")

    st.write("This app is a quick example showing how you can use LangGraph Cloud in your development applications. \
            Before playing with the app, I highly recommend reading through this info guide to gain a better understanding of how it works.")
    
    st.header("Background")

    st.write("This app was designed to show off some LangGraph Cloud features in a fun, interactive way. This app is designed to allow users to write a story \
             with the help of a LangGraph agent. The app allows users to edit chapters they have written already, or continue the story by writing \
             the next chapter as well. This means the user could have multiple versions of the same chapter number (for example chapter #3) and can select the \
             one they like most to continue writing chpater #4. At the beginning the user provides the graph information on the summary of the story, the writing style \
             they want, and any additional details important to the story. From that point on they just need to provide edit and continue instructions to steer the \
             agent in the desired direction")
    
    st.header("The Graph State")

    st.write("One of the coolest features of LangGraph Cloud is the ability to have a persistent state across many runs of the graph. \
             In this case we are able to retain information about the story as the user continues to write it. In our case, we keep an overall \
             chapter state graph, which is just a dictionary containing the different chapter written so far. Each time you edit or continue the \
             story a new chapter is added to the graph. Each chapter keeps information about its content, title, and the relationship it has with \
             the other chapters in the story (i.e. what chapters are siblings, children, parents, or cousins to it). Below is an example of what the \
             chapter graph would look like after a user has been using the Story Writing tool for a little bit:")
    
    st.image('./img/Flowchart.jpg')
    
    st.write("Let's dive into the graph to understand it a little better. First note that each color represents a different chapter number. In this instance \
             we have two Chapter 1's, two Chapter 2's, three Chapter 3's, and a single Chapter 4. By following the node numbers we can reconstruct how this story \
             was written. First, Node 1 was created when the user clicked on \"New Story\". Then Node 2 was created when the user pressed \"Continue\". The user \
             then created Node 3 by editing the chapter that was contained in Node 1. You can follow the rest of the story creation on your own by tracking the \
             increasing node numbers.") 
             
    st.write("When using the story app, you can navigate between previous chapters, next chapters, current chapters. It can be a little confusing to understand \
             what chapters show up where, so let's take a look at an example where the user is currently viewing the chapter in Node 5. The following diagram \
             highlights the relationships Node 5 has with other nodes, and the explanation below dives into how these relationships work and how they inform \
             what previous, next, and current chapter options we have to choose from:")
    
    st.image('./img/Flowchart-2.jpg')
    

    st.write("In this diagram, we draw \
             red arrows representing all of the other nodes the user could move to.  \n  \nThere is one \"Next Chapter\" option, Node 8, because Node 5 only has \
             one child. If we were to press \"Continue\" again from Node 5 to create another child, there would then be two options for the \"Next Chapter\".  \n  \nThere\
              are three current chapter options. The first is Node 5 itself (the chapter you are viewing is always an option to be the current chapter!) \
             and then Nodes 6 and 7 are also options. Node 7 is a \"Sibling\" of Node 5 because it was created by editing from Node 5. If we were to further make \
             an edit to Node 7, that new node would also be a siblig of Node 5. Any nodes that are direct \"edit descendants\" of a node are considered \"Siblings\" \
             of that node.  \n  \nNode 6 is what we call a \"Cousin\" node because it originates from the same node as Node 5 (namely Node 4) but is not directly \
             connected to it on our flow chart. Any nodes that originate from the same parent as a particular node are considered \"Cousin\" nodes. To summarize: \
             the \"Current Chapter\" options consist of the current node itself, all of its \"Sibling\" nodes, and all of its \"Cousin\" nodes. \n\
             Lastly, you can (unless you are at a node representing a Chapter 1 - in this case Node 1 and Node 3) go back to the previous chapter. Unlike the \
             current or next chapter options, there is always only one previous chapter to go back to: your direct parent. For Node 5, its direct parent is \
             Node 4, so that would show up as the option for the previous chapter.  \n  \nOne last important thing to note is that chapter options are displayed by their \
             chapter title, which makes it slightly easier to know where you are going instead of relying on node numbers which don't have much significance to the user.")
    
    st.header("Using the app")

    st.subheader("While viewing a chapter")

    st.write("There are a variety of different things to navigate through while using the app, let's walk through them by exploring this screenshot:")

    st.image("./img/story_writing_screenshot.png")

    st.write("At the top of the page you will see the title of the story, which is generated by the graph when the user starts the story. When you click on the \"Load Story\" \
             button on the left hand navigation pane, stories are listed by their titles to make it easier for users to remember which story they are loading.  \n  \nBelow the \
             story title, there are two dropdowns for selecting the previous or next chapter to navigate to. These only show up as dropdowns if there exist chapters \
             to move to, otherwise text saying \"No next/previous chapters!\" will show up.  \n  \nBelow those dropdowns, you can see the current chapter title. Chapter \
             titles are generated by the graph after the chapter has been written to try and allow the title to match the chapter content as much as possible.  \n  \nBelow \
             the chapter title is the actual chapter content itself. The chapter content is inside a scrollable element to limit the amount of vertical space it takes up.  \n  \nBelow \
             the chapter content is the chapter number. In this screenshot we are on Chapter 2 (remember from the node diagram that we can have multiple of a single chapter)")

    st.subheader("While the graph is running")

    st.image("./img/story_writing_graph_running.png")

    st.header("Ideas for future work")

    st.write("This ")

if __name__ == "__main__":
    asyncio.run(main())
