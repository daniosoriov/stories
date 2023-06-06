import ConnectOpenAI
import streamlit as st
from google.oauth2 import service_account
from gsheetsdb import connect
import variables

# from st_files_connection import FilesConnection

# Create a connection object.
credentials = service_account.Credentials.from_service_account_info(
    st.secrets["gcp_service_account"],
    scopes=[
        "https://www.googleapis.com/auth/spreadsheets",
    ],
)
conn = connect(credentials=credentials)


# Perform SQL query on the Google Sheet.
# Uses st.cache_data to only rerun when the query changes or after 10 min.
@st.cache_data(ttl=600)
def run_query(query):
    rows = conn.execute(query, headers=1)
    rows = rows.fetchall()
    return rows


sheet_url = st.secrets["private_gsheets_url"]
rows_sheet = run_query(f'SELECT * FROM "{sheet_url}"')

# Print results.
for row in rows_sheet:
    st.write(row)
    # st.write(f"{row.name} has a :{row.pet}:")

# Setting up the sidebar
st.sidebar.header('How to use')
st.sidebar.markdown(variables.sidebar_how_to_use)
st.sidebar.divider()

st.sidebar.header('FAQ')
for element in variables.faq:
    for type_text, text in element.items():
        if type_text == 'question':
            st.sidebar.subheader(text)
        elif type_text == 'answer':
            st.sidebar.write(text)

st.title('Story Sprout')
st.subheader('Create respectful stories for children aged 2-6 using OpenAI GPT-4')
st.divider()

connect_openai = ConnectOpenAI.ConnectOpenAI(api_key=st.secrets['OPENAI_KEY'],
                                             instruction=st.secrets.stories.system_prompt)


def create_prompt_section():
    with st.expander(label='Prompt', expanded=True):
        st.write(variables.prompt_language_text)
        st.text_area('Short description', max_chars=400, key='user_message', help=variables.prompt_text_area_help,
                     placeholder='Write a story about...')
        st.number_input('Age of the child?', min_value=2, max_value=6, step=1, format='%d', key='age',
                        help=variables.prompt_age_help)
    st.button('Generate a story', on_click=check_prompt)
    st.divider()


def check_prompt():
    """ Do all the checks here before preparing the story """
    # Checking that the prompt is not empty
    if not st.session_state.user_message:
        prompt_error = variables.prompt_no_text_error
    # If we have a prompt, moderate it
    else:
        # If the prompt is flagged, we show an error message
        if not connect_openai.moderate_message(st.session_state.user_message, test=True, test_flagged=True):
            prompt_error = variables.prompt_flagged_error
        else:
            prompt_error = False
    st.session_state.prompt_error = prompt_error


def generate_story():
    user_message = f'{st.session_state.user_message}\n\nMake the story for a {st.session_state.age} year old.'
    story_text, finish_reason = connect_openai.create_story(user_message=user_message, test=True, wait_time=4)
    story_warning_text = None
    match finish_reason:
        case 'length':
            story_warning_text = 'The response was cut off because it was too long.'
        case 'content_filter':
            story_warning_text = 'The story is not respecting OpenAI\'s usage policies.'
    st.session_state.story_warning = story_warning_text
    st.session_state.story = story_text


def create_feedback_section():
    st.write(variables.rate_msg)
    st.session_state['feedback'] = st.radio('Help us by rating this story', range(6),
                                            horizontal=True,
                                            format_func=lambda x: variables.rate_options.get(x))
    st.session_state['additional_comments'] = st.text_area("Additional comments:")
    st.button("Submit Feedback", on_click=provide_feedback)


def provide_feedback():
    st.session_state.feedback_given = True


def restart_app():
    for key in st.session_state.keys():
        del st.session_state[key]


if 'story' not in st.session_state:
    st.session_state.story = ''
if 'prompt_error' not in st.session_state:
    st.session_state.prompt_error = None
if 'story_warning' not in st.session_state:
    st.session_state.story_warning = None
if 'feedback_given' not in st.session_state:
    st.session_state.feedback_given = False

create_prompt_section()
if st.session_state.prompt_error is not None:
    if st.session_state.prompt_error:
        st.error(st.session_state.prompt_error)
    else:
        if not st.session_state.story:
            with st.spinner('Creating your story, please be patient...'):
                generate_story()
                if st.session_state.story_warning:
                    st.warning(st.session_state.story_warning)
                st.success("Here's your story!")

        st.write(st.session_state.story)
        st.divider()
        if not st.session_state.feedback_given:
            create_feedback_section()
        else:
            st.info('Thank you for your feedback!')
            st.button("Create another story?", on_click=restart_app)
