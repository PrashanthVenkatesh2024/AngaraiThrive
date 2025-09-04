# importing libraries
import os
import base64
from datetime import datetime
from urllib.parse import quote as urlquote
import dash
from dash import dcc, html, Input, Output, State, callback, no_update
from dash.exceptions import PreventUpdate
from dash.dependencies import ALL
import dash_bootstrap_components as dbc
from firebase_admin import firestore, storage
import pandas as pd 

# Declares directories used
UPLOAD_DIR = "uploads"
REPORTS_DIR = "reports"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(REPORTS_DIR, exist_ok=True)

#Variables to store CSS-based style attribute dictionaries 
tabs_style = {'borderBottom': 'none'}
tab_style = {
    'border': 'none',
    'padding': '10px',
    'fontWeight': 'bold',
    'color': "#000000"  
}
tab_selected_style = {
    'border': 'none',
    'borderTop': '3px solid #dc3545', 
    'padding': '10px',
    'fontWeight': 'bold',
    'color': 'white', 
    'backgroundColor': 'transparent'
}

#Function for displaying home page
def home_layout():
    return html.Div(
        style={
            'backgroundColor': "#cbe5ff", 
            'minHeight': '100vh',
            'display': 'flex',
            'flexDirection': 'column',
            'justifyContent': 'space-between'
        }, #Setting home page's style attributes
        children=[ #children refers to componenets inside the main home layout
            html.Div(id='tab-content', className='p-4', style={'flex': '1'}), #Setting the dynamic sized space for the tab's conentent
            dcc.Tabs(
                id='home-tabs',
                value='tab-generate', #for referring to in callbacks
                children=[
                    dcc.Tab( #Generate Report Tab
                        label='Generate Report',
                        value='tab-generate',
                        style=tab_style,
                        selected_style=tab_selected_style
                    ),
                    dcc.Tab( #Past-Reports tab
                        label='Past Reports',
                        value='tab-past',
                        style=tab_style,
                        selected_style=tab_selected_style
                    )
                ],
                style=tabs_style,
                className="bg-primary shadow-sm rounded-top"  #Small Dropshadow and Rounded top corners
            )
        ]
    )

def register_callbacks(app):
    @app.callback(
        Output('upload-data', 'children'),
        Input('upload-data', 'filename'),
        Input('upload-data', 'contents'),
        prevent_initial_call=True,
        allow_duplicate=True #allows mutliple callbacks to same output location
    )
    #Function to control the upload csv area of the tab
    def update_upload_area(filename, contents): 
        if not filename or not contents:
            return html.Div(['Drag and Drop or ', html.A('Select a CSV File')]) #When no file is uploaded, prompt user to upload csv

        data = contents.split(',')[1] #Processes csv by separating its contents based on commas
        with open(os.path.join(UPLOAD_DIR, filename), 'wb') as fp: #Opens file system on user's device, allowing uploading of csv
            fp.write(base64.b64decode(data)) #Converts file to binary and writes to the uploads directory

        return html.Div(
            style={'textAlign': 'center'},
            children=[
                html.I("✔", className="text-success", style={"fontSize": "2rem"}),
                html.Br(),
                html.Div("Click here to upload a different CSV", className="text-muted mt-2")
            ]
        ) #Successful CSV Upload Display

    @app.callback(
        Output('tab-content', 'children'),
        Input('home-tabs', 'value'),
        allow_duplicate=True
    )
    #Function for rendering overall tab content
    def render_tab_content(active_tab):
        if active_tab == 'tab-generate': #Generate Report Tab
            return html.Div(
                className="text-center",
                children=[
                    html.H2([ 
                        html.Img(src='assets/AngaraiLogo.jpeg', style={"height": "48px", "marginRight": "10px", "verticalAlign": "middle"}, alt="Logo"),
                        "Thrive"
                    ], className="mb-4"),
                    dcc.Upload(
                        id='upload-data',
                        children=html.Div(['Drag and Drop or ', html.A('Select CSV File')]),
                        style={
                            'width': '100%',
                            'maxWidth': '600px',
                            'minHeight': '150px',
                            'borderWidth': '2px',
                            'borderStyle': 'dashed',
                            'borderRadius': '10px',
                            'textAlign': 'center',
                            'margin': 'auto',
                            'backgroundColor': '#ffffff',
                            'display': 'flex',
                            'alignItems': 'center',
                            'justifyContent': 'center'
                        },
                        multiple=False,
                        accept='.csv'
                        
                    ),
                    dbc.Button(
                        "Generate Report",
                        id="generate-btn",
                        color="primary",
                        className="mt-4 btn-lg shadow",
                        disabled=True
                    ) #Generate Report button
                ]
            )#Displays the generate report button along with upload csv button with style elements

        elif active_tab == 'tab-past': #Past-reports tab
            # Dropdown for sorting Past Reports
            sort_dropdown = html.Div(
                className="d-flex justify-content-end align-items-center mb-3", #Flexible display size with children aligned vertically and a bottom margin of 3 units
                children=[
                    html.Div("Sort by date:", className="me-2"),
                    dcc.Dropdown(
                        id='sort-order-dropdown',
                        options=[
                            {'label': 'Latest first', 'value': 'desc'}, #Refers to descending order of date and time
                            {'label': 'Oldest first', 'value': 'asc'} #Refers to ascending order of date and time
                        ],
                        value='desc', #Default is latest first
                        clearable=False, #Doesn't allow for dropbox to be blank
                        style={'width': '150px'}
                    )
                ]
            )
            # Fetch Firestore Documents from Firestore database(for file references) and storage(for actual files)
            db = firestore.client() #Creates variable db that acts as the client using firestore
            docs = db.collection("reports").stream() #Creates variable docs to dtore the entreis in the firebase reports collection
            report_entries = [] 
            for doc in docs:
                data = doc.to_dict() #Converts each file in firebase to a dictionary
                ts = data.get("timestamp") #stores timestamp of file
                #Normalizing ts into python datetime object ts_dt
                if isinstance(ts, str): #if the datetime is a string
                    ts_dt = datetime.strptime(ts, "%Y-%m-%d_%H-%M-%S") #Converts timestamp to YYYY-MM-DD
                else: 
                    ts_dt = ts.to_datetime() if hasattr(ts, 'to_datetime') else ts #checks if ts has a method 'to_datetime' and uses it - As in the case of pandas datestamps 
                report_entries.append({
                    'ts': ts_dt,
                    'filename': data.get("filename"),
                    'pdf_path': data.get("pdf_path") or "" #If path not available, it is blank
                }) #Adds file info encapsulated as one entry into the report_entries dictionary

            #Sorting entries by date 
            report_entries.sort(key=lambda x: x['ts'], reverse=True) #Sorting, lamda tells python to use 'ts' as the value to compare when sorting
            #Default sorting is ascending - reverse allows to swap it to descending, which provides latest report first as default
            
            cards = [] #Creating cards for all the reports
            for i, entry in enumerate(report_entries): #enumerate allows iteration through the report_entries dictionary
                #Storing date and time stamps, file name, and path of each entry in report_entries
                date_str = entry['ts'].strftime("%Y-%m-%d %H:%M:%S") 
                filename = f"AngaraiThriveReport_{entry['ts'].strftime('%Y-%m-%d')}"  #Set's File Name
                pdf_path = entry['pdf_path']
                icon_id = f"dl-icon-{i}" #Icon id based on position in report_entires - loop variable i gives position
                #f tells python it is a formatted string literal

                btn_id = {'type': 'download-btn', 'index': i, 'pdf_path': pdf_path} 
                #Encapsulated the functioning of the download button to btn-id allowing reusability of the button

                cards.append(
                    html.Div( #Generates the cards for all reports
                        className="border rounded p-3 mb-3 bg-white shadow-sm",
                        children=[
                            html.Div(
                                className="d-flex justify-content-between align-items-center",
                                children=[
                                    html.Div([
                                        html.Div(filename, className="fw-bold"),
                                        html.Div(date_str, className="text-muted small")
                                    ]),
                                    dbc.Button(
                                        [html.I(className="bi bi-download me-1", id=icon_id), "Download PDF"],
                                        id=btn_id,
                                        color="primary",
                                        outline=True,
                                        size="sm",
                                        n_clicks=0,
                                        disabled=(pdf_path == "")
                                    ) #Downloads Report button
                                ]
                            ),
                            dbc.Tooltip("Download report PDF", target=icon_id) #Hovering over download icon reveals message : "Download report PDF"
                        ]
                    )
                )

            if not cards:
                container_children = html.Div("No reports yet.", className="text-center text-muted") #When no reports have been generated yet
            else:
                container_children = cards #Assigning cards variable to contianer_children

            cards_container = html.Div(container_children, id='reports-list-container') #Setting the main division of the past-reports tab to container_children
            download_component = dcc.Download(id="download-pdf-past") #Used for downloading the pdf onto user system

            return html.Div([sort_dropdown, cards_container, download_component]) #returns page elements of past_reports

        else:
            return html.Div() #returns empty page for exception circumstances

    @app.callback(
        Output('generate-btn', 'disabled'),
        Input('upload-data', 'contents'),
        allow_duplicate=True
    )
    #Generates content on Generate Report tab only after the csv is uplaoded
    def toggle_generate(contents):
        return contents is None

    @app.callback(
        [Output('home-tabs', 'value'), Output('url', 'pathname')],
        Input('generate-btn', 'n_clicks'),
        State('upload-data', 'filename'),
        prevent_initial_call=True,
        allow_duplicate=True
    )
    #Generates pdf, saves to firebase, and redirects to report page
    def generate_and_switch(n_clicks, filename):
        if not n_clicks or not filename:
            raise PreventUpdate #No change if generate_report isn't clicked

        db = firestore.client()
        bucket = storage.bucket() #Firestore Storage Bucket for storing the pdfs of reports
        csv_path = os.path.join(UPLOAD_DIR, filename)  #Declaring path to save csv 
        with open(csv_path, 'rb') as f: #Opens pdf in binary read mode as dynamic variable f
            csv_bytes = f.read() #Stores data in f, the csv, in csv_bytes
        
        df = pd.read_csv(csv_path)  # USes pandas to read csv
        date_cols = [c for c in df.columns if any(x in c.lower() for x in ['date', 'time', 'timestamp'])] #Checks for a date time column
        if date_cols:  # if any date and time column exists
            date_col = None  
            for key in ['timestamp', 'date', 'time']:  #Looks for key words among the columns
                for col in date_cols:  
                    if key in col.lower(): 
                        date_col = col  
                        break  
                if date_col:  
                    break 
            series = pd.to_datetime(df[date_col], errors='coerce', infer_datetime_format=True)  #Converts column data to datetime format
            series = series.dropna()  #removes NaN values
            if not series.empty:  #If column isn't empty
                last_ts_dt = series.max()  #Finds latest value - maximum value 
                if pd.isna(last_ts_dt) or (hasattr(last_ts_dt, 'year') and last_ts_dt.year < 2000): 
                    last_ts_dt = datetime.now()  #If date and time does not exist or is out of bounds, takes date and time of upload
            else:  
                last_ts_dt = datetime.now()
        else: 
            last_ts_dt = datetime.now()  #for all exceptions, takes current date and time at time of upload
        ts_str = last_ts_dt.strftime("%Y-%m-%d_%H-%M-%S") #Setting timestamp of pdf

        #Uploading csv to firestore stroage bucket
        bucket.blob(f"reports/{ts_str}_{filename}")\
              .upload_from_string(csv_bytes, content_type='text/csv') #Uploads the csv to the reports storage location in the Firestore Storage Bucket

        #Uploading PDF to firesotre storage bucket 
        pdf_name  = f"AngaraiThriveReport_{last_ts_dt.strftime('%Y-%m-%d')}.pdf"  #Set's pdf name
        pdf_bytes = b"%PDF-1.4\n%placeholder\n"
        bucket.blob(f"reports/{ts_str}_{pdf_name}")\
              .upload_from_string(pdf_bytes, content_type='application/pdf')

        # Stores data of the pdf including timestamp to the reports database in firebase
        db.collection("reports").add({
            "timestamp":    ts_str,
            "filename":     filename,
            "storage_path": f"reports/{ts_str}_{filename}",
            "pdf_path":     f"reports/{ts_str}_{pdf_name}"
        })
        return 'tab-past', '/report' #Redirects to reports

    @app.callback(
        Output('download-pdf-past', 'data'),
        Input({'type': 'download-btn', 'index': ALL, 'pdf_path': ALL}, 'n_clicks'),
        prevent_initial_call=True,
        allow_duplicate=True
    )
    #PDF Download 
    def trigger_pdf_download(n_clicks_list):
        if not any(n_clicks_list):
            raise PreventUpdate

        ctx = dash.callback_context #Identifying which card's button was clicked
        trigger_id = ctx.triggered_id #Finding id of the card that triggered pdf download
        if not trigger_id:
            raise PreventUpdate #If no card triggeerd, no changes
        pdf_path = trigger_id.get('pdf_path') #Gets path of the pdf from card id
        if not pdf_path:
            raise PreventUpdate #If no pdf exists at filepath, no changes

        #Fetch the PDF File from Firebase Storage
        blob = storage.bucket().blob(pdf_path) #Fetches the Storage Bucket Blob of the pdf based on the pdf_path
        pdf_bytes = blob.download_as_bytes() #Converts the blob to bytes
        filename = os.path.basename(pdf_path) #Extracts only final filename from the entire path

        return dcc.send_bytes(pdf_bytes, filename=filename) #Send the bytes of the pdf to dash for download from browser to user device
