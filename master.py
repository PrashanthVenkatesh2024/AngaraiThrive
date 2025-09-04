#Importing dash, dash_bootstrap and firbase libraries
from dash import Dash, dcc, html, Input, Output
import dash_bootstrap_components as dbc
import firebase_admin
from firebase_admin import credentials, firestore, storage

#Importing functions from the different pages of the app
from home_page import home_layout, register_callbacks as home_callbacks
from generate_report import report_layout, register_callbacks as report_callbacks
from login_page import login_layout, register_callbacks as login_callbacks
from register_page import register_layout, register_callbacks as reg_callbacks

#Initializing Firebase Admin to the entire app
cred = credentials.Certificate("firebase_key.json")
firebase_admin.initialize_app(cred, {
    'storageBucket': 'angaraithrive.firebasestorage.app'
})

app = Dash(
    __name__,
    external_stylesheets=[dbc.themes.FLATLY],
    suppress_callback_exceptions=True #Ensuring only essential callback errors are considered
)#Initializing the app
app.title = "AngaraiThrive"
server = app.server  

app.layout = html.Div([
    dcc.Location(id='url', refresh=False),
    html.Div(id='page-content')
]) #Setting app to use html elements for UI

@app.callback(
    Output('page-content', 'children'),
    Input('url', 'pathname')
)#Setting route and definition for callbacks across the app

def display_page(pathname):
    if pathname == '/register':
        return register_layout()
    #if pathname == '/login':
        #return login_layout()
    if pathname == '/home':
        return home_layout()
    if pathname == '/report':
        return report_layout()
    return login_layout() #default when app is opened
#Declaring function for displaying pages across the app 

#Setting page specific callbacks
login_callbacks(app)
reg_callbacks(app)
home_callbacks(app)
report_callbacks(app)


#Running the app
if __name__ == "__main__":
    app.run(debug=True)