# Story Sprout

A children's story generation application

This repository contains a web-based interactive application for generating and reviewing stories using Streamlit and
OpenAI's language model with GPT 4.

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://storysprout.streamlit.app)

## Features

- **Story Prompt Creation**: Users can create a story prompt and specify the age of the intended reader.

- **Story Generation**: The application generates a unique story based on the user-provided prompt.

- **Story Feedback**: Users can provide feedback on generated stories, helping to improve future story generation.

## Files

The main files in this repository are:

- `main.py`: The main application file which handles user inputs, story generation, and feedback.
- `ConnectOpenAI.py`: A class to make calls to the OpenAI's API.
- `variables.py`: A file to hold most of the text for the application.

## Usage

1. Clone this repository to your local machine.
2. Install all necessary packages found in `requirements.txt`.
3. You need to create a file under `.streamlit/secrets.toml` with the secrets for your application.
    1. All secrets can be found by checking `st.session_state.secrets` inside of `main.py`.
4. Run the `main.py` file using Streamlit's command line instruction:

```commandline
streamlit run main.py
```

## Dependencies

- Python 3.11+
- Streamlit
- OpenAI API

## Contributing

If you'd like to contribute, please fork the repository and use a feature branch. Pull requests are warmly welcome.

## License

This project is licensed under the MIT License.