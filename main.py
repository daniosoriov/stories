from typing import List

import ConnectOpenAI
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import datetime
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import variables

scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
]

skey = st.secrets["gcp_service_account"]
credentials = Credentials.from_service_account_info(
    skey,
    scopes=scopes,
)
client = gspread.authorize(credentials)


def spreadsheet_save_data(data: List, sheet_name: str = "Results") -> bool:
    """
    Saves data (the prompt and the generated story) to a Google Sheets worksheet.

    This method appends a new row to the specified Google Sheets worksheet with the provided data list.
    It requires that we have valid credentials for accessing the Google Sheets API.

    :param data: The list of data to append as a new row to the worksheet.
    This list should contain the prompt and the generated story.
    :param sheet_name: The name of the worksheet where the data will be appended.
    If not provided, the default worksheet name is "Results".
    :return: True if the operation was successful, False otherwise.
    """
    try:
        sh = client.open_by_url(st.secrets["private_gsheets_url"])
        worksheet = sh.worksheet(sheet_name)
        worksheet.append_row(data)
        return True
    except Exception as e:
        print(f"Error while saving data to spreadsheet: {e}")
        return False


# Configuring the page
st.set_page_config(page_title=variables.page_title, page_icon="📚", menu_items=variables.menu_items)

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
st.subheader('Create respectful stories for children between 0 and 8 years old')
st.divider()

connect_openai = ConnectOpenAI.ConnectOpenAI(api_key=st.secrets['OPENAI_KEY'],
                                             instruction=st.secrets.stories.system_prompt)


def format_email_text(**kwargs):
    lines = []
    for key, val in kwargs.items():
        lines.append(f"<strong>{key}</strong>")
        lines.append(str(val))
        lines.append('')
    return lines


def send_email(message: list) -> None:
    """
    Sends an email message
    :param message: The lines of the message
    :return: None
    """
    sender_name = st.secrets.smtp.SENDER_NAME
    sender_email = st.secrets.smtp.SENDER_EMAIL
    sender_email_complete = f"{sender_name} <{sender_email}>"
    receiver_name = st.secrets.smtp.RECIPIENT_NAME
    receiver_email = f"{receiver_name} <{st.secrets.smtp.RECIPIENT_EMAIL}>"
    password = st.secrets.smtp.SENDER_PASSWORD
    today = datetime.datetime.today()
    subject = f"New story created, {today.strftime('%F %T')}"
    message = '<br />\n'.join(message)

    msg = MIMEMultipart()
    msg['From'] = sender_email_complete
    msg['To'] = receiver_email
    msg['Subject'] = subject

    body = f"""
        <html>
        <body>
        {message}
        </body>
        </html>
        """

    msg.attach(MIMEText(body, 'html'))

    with smtplib.SMTP('smtp.gmail.com', 587) as server:
        server.starttls()
        server.login(sender_email, password)
        server.sendmail(sender_email, receiver_email, msg.as_string())


def create_prompt_section():
    with st.expander(label='Create your story', expanded=True):
        st.text_area('What is your story about?', max_chars=400, key='user_message',
                     help=variables.prompt_text_area_help,
                     placeholder='Write a story about a child named... who had a ... and now is ...')
        st.caption(variables.prompt_caption)
        st.number_input('Age of the reader?', min_value=0, max_value=8, value=4, step=1, format='%d', key='age',
                        help=variables.prompt_age_help)
    st.button('Generate story', on_click=check_prompt)
    st.caption(variables.prompt_button_caption)
    st.divider()


def check_prompt():
    """ Do all the checks here before preparing the story """
    # Checking that the prompt is not empty
    if not st.session_state.user_message:
        prompt_error = variables.prompt_no_text_error
    # If we have a prompt, moderate it
    else:
        # If the prompt is flagged, we show an error message
        test = bool(st.secrets.stories.test_moderation)
        flagged = bool(st.secrets.stories.test_moderation_flagged)
        if connect_openai.moderate_message(st.session_state.user_message, test=test, test_flagged=flagged):
            prompt_error = variables.prompt_flagged_error
        else:
            prompt_error = False
    st.session_state.prompt_error = prompt_error


def generate_story():
    user_message = f'{st.session_state.user_message}.\n\nMake the story for a {st.session_state.age} year old.'
    test = bool(st.secrets.stories.test_story)
    wait_time = bool(st.secrets.stories.test_wait_time)
    reason = st.secrets.stories.test_reason
    story_text, finish_reason = connect_openai.create_story(user_message=user_message, test=test,
                                                            test_reason=reason, wait_time=wait_time)
    story_warning_text = None
    if finish_reason == 'length':
        story_warning_text = 'The response was cut off because it was too long.'
    elif finish_reason == 'content_filter':
        story_warning_text = 'The story is not respecting OpenAI\'s usage policies.'
    st.session_state.user_message_complete = user_message
    st.session_state.story_warning = story_warning_text
    st.session_state.story = story_text
    st.session_state.stories.append(story_text)
    data = {
        'user_message': st.session_state.user_message,
        'age': st.session_state.age,
        'user_message_complete': st.session_state.user_message_complete,
        'story': st.session_state.story,
        'finish_reason': finish_reason,
        'total_tokens': connect_openai.total_tokens,
    }
    spreadsheet_save_data(list(data.values()))
    if st.secrets.smtp.SEND_EMAIL:
        lines = format_email_text(**data)
        send_email(lines)


def create_feedback_section():
    st.write(variables.rate_msg)
    st.session_state['feedback'] = st.radio('Help us by rating this story', range(6),
                                            horizontal=True,
                                            format_func=lambda x: variables.rate_options.get(x))
    st.session_state['additional_comments'] = st.text_area("Additional comments:")
    st.button("Submit Feedback", on_click=provide_feedback)


def provide_feedback():
    data = {
        'user_message': st.session_state.user_message,
        'age': st.session_state.age,
        'user_message_complete': st.session_state.user_message_complete,
        'story': st.session_state.story,
        'feedback': st.session_state.feedback,
        'additional_comments': st.session_state.additional_comments,
    }
    spreadsheet_save_data(list(data.values()), 'Feedback')
    st.session_state.feedback_given = True


def restart_app():
    for key in st.session_state.keys():
        del st.session_state[key]


if 'story' not in st.session_state:
    st.session_state.story = ''
if 'stories' not in st.session_state:
    st.session_state.stories = []
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
        # if not st.session_state.story:
        with st.spinner('Creating your story, please be patient...'):
            generate_story()
            if st.session_state.story_warning:
                st.warning(st.session_state.story_warning)
            st.success("Here's your story!")
        for num in range(len(st.session_state.stories), 0, -1):
            expanded = True if (num == len(st.session_state.stories)) else False
            with st.expander(label=f'Story #{num}', expanded=expanded):
                st.write(st.session_state.stories[num - 1])
        if not st.session_state.feedback_given:
            create_feedback_section()
        else:
            st.info('Thank you for your feedback!')
        st.button("Clean stories and start again?", on_click=restart_app)
