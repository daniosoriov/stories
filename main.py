from typing import List, Dict
import ConnectOpenAI
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import datetime
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import variables
import random

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

st.sidebar.image('img/bmc_qr.png', width=200)

# Main section
st.title('Story Sprout')
st.subheader('Create respectful stories for children up to 8 years old')

# Removing the borders created by the styling of the forms
css = r'''
    <style>
        [data-testid="stForm"] {
            border: 0px;
            padding: 0px;
        }
    </style>
'''
st.markdown(css, unsafe_allow_html=True)

# Selecting the instructions we will use for A/B testing
INSTRUCTIONS = {instruction_name: st.secrets.stories[instruction_name] for instruction_name in
                st.secrets.stories.instructions}
# Initializing the connection to OpenAI
connect_openai = ConnectOpenAI.ConnectOpenAI(api_key=st.secrets['OPENAI_KEY'])


def format_email_text(**kwargs) -> List:
    """
    Formats a message for an email

    :param kwargs: The parameters to include in the email
    :return: lines in HTML format for the email
    """
    lines = []
    for key, val in kwargs.items():
        lines.append(f"<strong>{key}</strong>")
        lines.append(str(val))
        lines.append('')
    return lines


def send_email(message: list, feedback: bool = False) -> None:
    """
    Sends an email message

    :param message: The lines of the message
    :param feedback: If the message to send is about a feedback received instead of a new created story
    :return: None
    """
    sender_name = st.secrets.smtp.SENDER_NAME
    sender_email = st.secrets.smtp.SENDER_EMAIL
    sender_email_complete = f"{sender_name} <{sender_email}>"
    receiver_name = st.secrets.smtp.RECIPIENT_NAME
    receiver_email = f"{receiver_name} <{st.secrets.smtp.RECIPIENT_EMAIL}>"
    password = st.secrets.smtp.SENDER_PASSWORD
    today = datetime.datetime.today()
    title = 'feedback received' if feedback else 'story created'
    subject = f"[Story Sprout] - New {title}, {today.strftime('%F %T')}"
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


def prompt_section() -> None:
    """
    Create the section for the user input

    This function creates a section in the Streamlit app for user input.
    The user can input details for creating a story.
    It includes a text area for story details and a number input for the age of the reader.
    When the form is submitted, it checks if the input is valid by moderating it through the OpenAI's moderation
    tool.

    :return: None
    """
    with st.expander('Create your story', expanded=True):
        with st.form('prompt'):
            st.text_area('What is your story about?', max_chars=400, key='user_message',
                         help=variables.prompt_text_area_help,
                         placeholder='Write a story about a child named... who had a ... and now is ...')
            st.caption(variables.prompt_caption)
            st.number_input('Age of the reader?', min_value=0, max_value=8, value=4, step=1, format='%d', key='age',
                            help=variables.prompt_age_help)
            submitted = st.form_submit_button("Generate story")
            st.caption(variables.prompt_button_caption)
            if submitted:
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


def generate_story() -> None:
    """
    This method generates a story based on the user's input and writes it to the session state.

    The function first constructs the user's message and then uses the connect_openai.create_story method to generate
    a story based on that message and a randomly chosen instruction.

    The function then gathers relevant data, stores it in a dictionary, and appends this to a list in the session state.
    Finally, it checks if it should save the data to a spreadsheet or send it in an email, and if so, does so.

    :return: None
    """
    user_message = f'{st.session_state.user_message}.\n\nMake the story for a {st.session_state.age} year old.'
    test = bool(st.secrets.stories.test_story)
    wait_time = st.secrets.stories.test_wait_time
    reason = st.secrets.stories.test_reason
    instruction_key = random.choice(list(INSTRUCTIONS.keys()))
    instruction = INSTRUCTIONS[instruction_key]
    story_text, finish_reason = connect_openai.create_story(user_message=user_message, instruction=instruction,
                                                            test=test, test_reason=reason, wait_time=wait_time)
    story_warning_text = None
    if finish_reason == 'length':
        story_warning_text = 'The response was cut off because it was too long.'
    elif finish_reason == 'content_filter':
        story_warning_text = 'The story is not respecting OpenAI\'s usage policies.'
    st.session_state.user_message_complete = user_message
    st.session_state.story_warning = story_warning_text

    data = {
        'user_message': st.session_state.user_message,
        'age': st.session_state.age,
        'user_message_complete': st.session_state.user_message_complete,
        'instruction_key': instruction_key,
        'instruction': instruction,
        'story': story_text,
        'finish_reason': finish_reason,
        'estimated_tokens': connect_openai.estimated_tokens,
        'total_tokens': connect_openai.total_tokens,
        'count': len(st.session_state.stories_data),
    }
    st.session_state.stories_data.append(data)
    if st.secrets.write_sheets:
        spreadsheet_save_data(list(data.values()))
    if st.secrets.smtp.SEND_EMAIL:
        lines = format_email_text(**data)
        send_email(lines)


def create_story_feedback_section(data: Dict) -> None:
    """
    This function generates a form section in Streamlit for users to provide feedback on the generated story.

    The feedback includes a numerical rating and optional additional comments.
    Once the user submits the feedback, the function updates the session state with this feedback and,
    if configured to do so, writes the feedback data to a spreadsheet and sends an email with the data.

    :param data: A dictionary containing the data of the story for which feedback is being collected.
    :return: None
    """
    with st.form(f"feedback-form-{data['count']}"):
        st.write(data['story'])
        st.divider()
        st.session_state['feedback'] = st.radio('Help us by rating this story', range(6),
                                                horizontal=True,
                                                format_func=lambda x: variables.rate_options.get(x))
        st.session_state['additional_comments'] = st.text_area("Additional comments:")
        st.caption(variables.rate_msg)
        if st.form_submit_button("Submit Feedback"):
            st.info('Thank you for your feedback!')
            st.session_state.stories_data[data['count']].update({
                'feedback': st.session_state.feedback,
                'additional_comments': st.session_state.additional_comments,
            })
            if st.secrets.write_sheets:
                spreadsheet_save_data(list(data.values()), 'Feedback')
            if st.secrets.smtp.SEND_EMAIL:
                lines = format_email_text(**data)
                send_email(lines, feedback=True)


def restart_app() -> None:
    """
    It restarts the app by removing all values from the session state

    :return: None
    """
    for k in st.session_state.keys():
        del st.session_state[k]


if 'stories_data' not in st.session_state:
    st.session_state.stories_data = []
if 'prompt_error' not in st.session_state:
    st.session_state.prompt_error = None
if 'story_warning' not in st.session_state:
    st.session_state.story_warning = None

prompt_section()
if st.session_state.prompt_error is not None:
    if st.session_state.prompt_error:
        st.error(st.session_state.prompt_error)
    else:
        st.divider()
        # If the prompt form was submitted, generate a story
        if st.session_state['FormSubmitter:prompt-Generate story']:
            with st.spinner('Creating your story can take some seconds, please be patient...'):
                generate_story()
                if st.session_state.story_warning:
                    st.warning(st.session_state.story_warning)
                st.success("Here's your story!")
        # Display all the stories that have been shared so far
        for num in range(len(st.session_state.stories_data), 0, -1):
            expanded = True if (num == len(st.session_state.stories_data)) else False
            with st.expander(label=f'Story #{num}', expanded=expanded):
                create_story_feedback_section(st.session_state.stories_data[num - 1])
        # Provide an option to clean all stories and start again
        st.button("Clean stories and start again?", on_click=restart_app)
