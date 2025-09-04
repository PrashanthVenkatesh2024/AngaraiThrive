# Importing Libraries
from dash import html, dcc, Input, Output, State, no_update
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
from firebase_admin import auth

def login_layout():
    return dbc.Container(
        [
            html.Div(id="login-redirect"), #page id
            dbc.Card( 
                [
                    dbc.CardHeader( #Header inside the bootstrap card
                        html.H2([ 
                            html.Img(src='assets/AngaraiLogo.jpeg', style={"height": "48px", "marginRight": "10px", "verticalAlign": "middle"}, alt="Logo"),
                            "Thrive"
                        ], className="text-center text-white"), #Using HTML elements for setting the home page layout
                        className="bg-primary" #Sets background to blue 
                    ),
                    dbc.CardBody( #The main body of the page
                        [
                            html.Div(id="login-prompt", className="text-success mb-3"), #Used for successful login - Sets css class to bootstrap default green and margin below to 3
                            dbc.Input(type="email", id="login-email", placeholder="Email", className="mb-3"), #Text Input Box for email - uses existing structures to ensure emails are entered
                            dbc.Input(type="password", id="login-password", placeholder="Password", className="mb-3"), #Password Entry box
                            html.Div(id="login-message", className="text-danger mb-3"), #Used for incorrect password or username entered with red as the color
                            dbc.Button("Login", id="login-button", color="primary", className="me-2"), #Login Button
                            html.Div(
                                [
                                    html.Span("No account? ", className="me-1"), #Span (Inline container to wrap text inside of) - 1 unit margin to the right
                                    dbc.Button("Register", href="/register", color="secondary") #Register Button with gray color - Redirect to register page on click
                                ],
                                className="mt-3" #Margin to the top of 3 unit
                            )
                        ]
                    )
                ],
                className="mx-auto mt-5", #Setting margins
                style={"maxWidth": "500px"} #Setting max width of the page's contents to 400 px for appropriate scaling
            )
        ]
    )

# Registering Callbacks
#Input changes being sent to specific outputs are callbacks
def register_callbacks(app):
    @app.callback(
        [
            Output("login-redirect", "children"), # Used for successful login redirects - A hidden container for login-redirect
            Output("login-message", "children") # Used for failed login messages
        ],
        [
            Input("login-button", "n_clicks"), #Registers clicks on the login button
            State("login-email", "value"), #Provides value of email
            State("login-password", "value")
        ],
        prevent_initial_call=True
    ) #These callbacks link to the requirements of the login function
    #Login function
    def login(n_clicks, email, password): 
        if not n_clicks:
            raise PreventUpdate #Prevents callback if login button is not clicked

        if not email or not password:
            return no_update, "Please enter both email and password." #Prevents login if either email or password isn't entered

        try:
            auth.get_user_by_email(email) #Checks with Firebase Auth service to see if the email and password are correct 
            #try will fail and go to except if any line inside fails
            return dcc.Location(id="login-redirect-loc", pathname="/home", refresh=True), "" #Redirect to home page on successful login
        except auth.UserNotFoundError: #Exception when user not found
            return no_update, "Invalid email or password. Please try again." #No redirect, update error message
        except Exception as e: #Other exceptions
            return no_update, f"Login failed: {e}" 

    @app.callback(
        Output("login-prompt", "children"), #Prompt to login post-redirect from register page
        Input("url", "search"),
        prevent_initial_call=False
    )
    def display_login_prompt(search):
        if search and "registered=1" in search: #Check if user just registered
            return "Registration successful! Please sign in."
        return "" #Empty return otherwise
