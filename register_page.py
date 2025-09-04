# Importing Libraries
from dash import html, dcc, Input, Output, State, no_update
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
from firebase_admin import auth

def register_layout():
    return dbc.Container(
        [
            html.Div(id="register-redirect"), #id for register page
            dbc.Card(
                [
                    dbc.CardHeader(
                        html.H2([ 
                            html.Img(src='assets/AngaraiLogo.jpeg', style={"height": "30px", "marginRight": "10px", "verticalAlign": "middle"}, alt="Logo"),
                            "AngaraiThrive - Register"  #Logo
                        ], className="text-center text-white"), #Centered Text
                        className="bg-primary" #Background color blue
                    ),
                    dbc.CardBody(
                        [
                            dbc.Input(type="text", id="register-name", placeholder="Full Name", className="mb-3"),
                            dbc.Input(type="email", id="register-email", placeholder="Email", className="mb-3"),
                            dbc.Input(type="password", id="register-password", placeholder="Password", className="mb-3"),
                            dbc.Input(type="password", id="register-confirm", placeholder="Confirm Password", className="mb-3"),
                            html.Div(id="register-message", className="text-danger mb-3"), #Red error message display box
                            dbc.Button("Register", id="register-button", href="/", color="primary"), #Redirect to Login Page when clicked
                            html.Div(
                                [
                                    html.Span("Already have an account? ", className="me-1"),
                                    dbc.Button("Login", href="/", color="secondary") #Login Page Redirect
                                ],
                                className="mt-3"
                            )
                        ]
                    )
                ],
                className="mx-auto mt-5",
                style={"maxWidth": "400px"}
            )
        ]
    )

# Registering Callbacks for Register Page
def register_callbacks(app):
    @app.callback(
        [
            Output("register-redirect", "children"),
            Output("register-message", "children")
        ],
        [
            Input("register-button", "n_clicks"),
            State("register-name", "value"),
            State("register-email", "value"),
            State("register-password", "value"),
            State("register-confirm", "value")
        ],
        prevent_initial_call=True
    )
    def register_user(n_clicks, name, email, password, confirm):
        if not n_clicks:
            raise PreventUpdate

        if not (name and email and password and confirm):
            return no_update, "Please fill out all fields."
        if password != confirm:
            return no_update, "Passwords do not match."

        try:
            auth.create_user(email=email, password=password, display_name=name)
            loc = dcc.Location(
                id="register-redirect-loc", 
                pathname="/",
                search="?registered=1",
                refresh=True
            )
            return loc, ""
        except auth.EmailAlreadyExistsError:
            return no_update, "This email is already registered."
        except Exception as e:
            return no_update, f"Registration failed: {e}"
