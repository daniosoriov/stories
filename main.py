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


def spreadsheet_save_prompt_and_story(data: List, sheet_name="Results"):
    sh = client.open_by_url(st.secrets["private_gsheets_url"])
    worksheet = sh.worksheet(sheet_name)
    worksheet.append_row(data)


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


def format_email_text(**kwargs):
    lines = []
    for key, val in kwargs.items():
        lines.append(f"<strong>{key}</strong>")
        lines.append(str(val))
        lines.append('')
    st.write(lines)
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
    user_message = f'{st.session_state.user_message}.\n\nMake the story for a {st.session_state.age} year old.'
    story_text, finish_reason = connect_openai.create_story(user_message=user_message, test=True, wait_time=4)
    story_warning_text = None
    if finish_reason == 'length':
        story_warning_text = 'The response was cut off because it was too long.'
    elif finish_reason == 'content_filter':
        story_warning_text = 'The story is not respecting OpenAI\'s usage policies.'
    st.session_state.user_message_complete = user_message
    st.session_state.story_warning = story_warning_text
    st.session_state.story = story_text
    data = {
        'user_message': st.session_state.user_message,
        'age': st.session_state.age,
        'user_message_complete': st.session_state.user_message_complete,
        'story': st.session_state.story,
        'finish_reason': finish_reason,
    }
    spreadsheet_save_prompt_and_story(list(data.values()))
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
    spreadsheet_save_prompt_and_story(list(data.values()), 'Feedback')
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
