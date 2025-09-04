# Importing libraries  #Importing libraries
import tempfile
import datetime
import matplotlib
matplotlib.use('Agg') #Helps rendering the pie chart
import matplotlib.pyplot as plt

from dash import dcc, html, Input, Output, State
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
import plotly.express as px

from sentiment_analysis import analyze_reviews, clean_html_text
from firebase_admin import firestore, storage
import pandas as pd
import string
from collections import Counter

from reportlab.platypus import SimpleDocTemplate, Paragraph, Image, Spacer, ListFlowable, PageBreak
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import letter
from io import BytesIO

def top_words(text):
    txt = clean_html_text(text).lower()
    txt = txt.translate(str.maketrans('', '', string.punctuation)) #removes punctuation
    stopwords = {"and","the","for","with","are","not","but","all","was","were","very","just","really",
                 "have","has","had","you","your","our","their","this","that","those","these",
                 "none","n/a","na","yes","out","too","they","i","we","on","in","of","to","at","from",
                 "great","good","excellent","amazing","awesome","nice",
                 "supportive","friendly","helpful","long","lack",
                 "job","work","company","many","some","one","well","lot","lots","make","makes","there","its","etc",
                 "employees","employee",
                 "minor","issue","issues","problem","problems",
                 "sometimes","often","better","major","could","working","lacking","high","low","inadequate",
                 "more","less","bad","poor","unfortunately"}
    words = [w for w in txt.split() if len(w) > 2 and w not in stopwords] #Extracting top most common key words from any geiven text excluding the stopwords
    return [w for w, _ in Counter(words).most_common(5)] #5 most common words

#Converting list of strings into readable sets of sentences
def list_to_text(lst):
    if not lst:
        return ''
    if len(lst) == 1:
        return lst[0]
    if len(lst) == 2:
        return f"{lst[0]} and {lst[1]}"
    return ", ".join(lst[:-1]) + f", and {lst[-1]}"

tabs_style = {'borderBottom': 'none'}
tab_style = {
    'border': 'none',
    'padding': '10px',
    'fontWeight': 'bold',
    'color': '#adb5bd'  
}
tab_selected_style = {
    'border': 'none',
    'borderTop': '3px solid #dc3545', 
    'borderBottom': '3px solid #dc3545', 
    'padding': '10px',
    'fontWeight': 'bold',
    'color': 'white', 
    'backgroundColor': 'transparent'
}

#Setting layout for the report
def report_layout():
    db = firestore.client() #Calling firebase database and saving the client call in ædb'
    bucket = storage.bucket() #Calling firestore storage and saving the bucket details in 'bucket'

    #fetching data of latest report 
    docs = (
        db.collection("reports")
          .order_by("timestamp", direction=firestore.Query.DESCENDING)
          .limit(1)
          .stream()
    )

    try:
        meta = next(docs).to_dict() #Converting the report metadata to a dictionary
    except StopIteration:
        return html.Div("No report found.", className="p-4", style={"backgroundColor": "#FFFFFF", "minHeight": "100vh"})  #When report does not exist and hence cannot be converted to dictionary

    #Determines display date and time from latest review timestamp 
    ts_val = meta.get("timestamp") 
    if isinstance(ts_val, str): 
        try:  
            last_dt = datetime.datetime.strptime(ts_val, "%Y-%m-%d_%H-%M-%S")  # Date and time stamp of latest review
        except Exception:  
            last_dt = datetime.datetime.now()  #if no date or time stamp is found, uses current date
    elif ts_val:  
        last_dt = ts_val.to_datetime() if hasattr(ts_val, 'to_datetime') else ts_val  #looks for datatypes that can be converted to date-time
    else:  
        last_dt = datetime.datetime.now()  # Uses current date and time as exception

    return html.Div([
        dbc.Row([
            dbc.Col(html.A("← Back to Home", href="/home", className="btn btn-outline-secondary"), width="auto"), #Back to home button with hyperlink redirected to home page
            dbc.Col(html.Div([
                html.H2([ 
                        html.Img(src='assets/AngaraiLogo.jpeg', style={"height": "48px", "marginRight": "10px", "verticalAlign": "middle"}, alt="Logo"),
                        "Thrive Sentiment Report"
                    ], className="mb-4"), 
                html.H6(f"Generated on {last_dt.strftime('%B %d, %Y')} at {last_dt.strftime('%H:%M:%S')}", className="text-center text-muted") #Timestamp
            ]), width=8),
            dbc.Col(html.Button("📄 Download PDF", id="download-btn", className="btn btn-success"), width="auto", className="text-end") #Download pdf button 
        ], className="mb-4 text-center"),

        dcc.Download(id="download-pdf"), #Telling dash (browser) to download output of a callback with this id

        dbc.Progress(id="upload-progress", value=100, striped=True, animated=True, label="Uploading...", color="primary", style={"width": "50%", "margin": "0 auto 1rem auto"}),  # ❌

        html.Div([
            dcc.Tabs(id="report-tabs", value="tab-general", children=[ #Creating tabs and navigation bar
                dcc.Tab(label="General", value="tab-general", style=tab_style, selected_style=tab_selected_style),
                dcc.Tab(label="Department", value="tab-dept", style=tab_style, selected_style=tab_selected_style),
                dcc.Tab(label="Job Tenure", value="tab-status", style=tab_style, selected_style=tab_selected_style),
            ], 
            style=tabs_style,
            className="bg-primary shadow-sm rounded-top"  #Small Dropshadow and Rounded top corners
            )
        ]),

        html.Div(id="tabs-content", className="p-4", style={"paddingBottom": "80px"}), #Division in page for the each tab's contents

        dcc.Interval(id="pdf-upload-interval", interval=1000, n_intervals=0, max_intervals=1), #Sets time gap of 1 second for the uplaod to take place before the confirmation is displayed
        #Triggered when a function with that callback id returns something - In this case, uploads to firestore storage
        dbc.Toast("Upload complete!", id="upload-toast", header="Upload Complete", icon="success",
                  is_open=False, duration=5000, dismissable=True,
                  style={"position": "fixed", "bottom": 10, "right": 10, "zIndex": 1000}) #popup message for 5 seconds when upload is complete
    ], style={"backgroundColor": "#cbe5ff", "minHeight": "100vh"})  # ❌

def register_callbacks(app):
    @app.callback(
        Output("tabs-content", "children"),
        Input("report-tabs", "value"),
        allow_duplicate=True
    )
    def render_tab(tab):
        db = firestore.client()
        bucket = storage.bucket()

        #Fetches latest report from firebase
        docs = (
            db.collection("reports")
              .order_by("timestamp", direction=firestore.Query.DESCENDING)
              .limit(1)
              .stream()
        )
        try:
            doc = next(docs) #Fetches next detail from the report in docs so details are fetched one at a time 
            #Done to prevent them all loading onto the memory at the same time 
        except StopIteration:
            raise PreventUpdate #When docs is fully scanned through, no change happen

        meta = doc.to_dict() #Converts the details to a dictionary
        blob = bucket.blob(meta["storage_path"]) #returns storage path of the report refered to by doc
        tmp = tempfile.NamedTemporaryFile(suffix=".csv", delete=False) #Creates a temporary csv
        blob.download_to_filename(tmp.name) #Downloads the contents of the firestore storage file onto the csv
        df = pd.read_csv(tmp.name) #pandas dataframe for the csv
        result = analyze_reviews(tmp.name) #Runs analyze_reviews function from sentiment analysis to get sentiment distribution details

        if tab == "tab-dept":
            dept_cols = [c for c in df.columns if 'dept' in c.lower() or 'department' in c.lower()]
            if dept_cols:
                dept_col = dept_cols[0]
                depts = sorted(df[dept_col].dropna().unique()) #Fetches all departments from the departments column in the csv, alphabetically sorted
            else:
                depts = sorted(result.get('department_sentiment', {}).keys()) #Get's department for which sentiment was analyzed if not department list was found
            options = [{"label": d, "value": d} for d in depts] #Creates dropdown options for department based categories 
            default = depts[0] if depts else None #default option is firstin the depts list
            return html.Div([
                dcc.Dropdown(id="dept-dropdown", options=options, value=default,
                             clearable=False, style={"width": "50%"}),
                html.Div(id="dept-content", className="mt-4") #Division to display report for that department 
            ])
        elif tab == "tab-status":
            status_cols = [c for c in df.columns if 'status' in c.lower()]
            if status_cols:
                status_col = status_cols[0]
                statuses = sorted(df[status_col].dropna().unique()) #Fetches all job statuses from the departments column in the csv, alphabetically sorted
                statuses = [str(s).capitalize() for s in statuses] #Fixes capitalization
            else:
                statuses = [s.capitalize() for s in result.get('status_sentiment', {}).keys()] #Get's job statuses for which sentiment was analyzed if not department list was found
            options = [{"label": s, "value": s.lower()} for s in statuses] #Creates dropdown options for job status based categories
            default = statuses[0].lower() if statuses else None #default option is firstin the statuses list
            return html.Div([
                dcc.Dropdown(id="status-dropdown", options=options, value=default,
                             clearable=False, style={"width": "50%"}),
                html.Div(id="status-content", className="mt-4") #Division to display report for that department
            ])
        else: #Overall sentiment
            labels = ['Positive', 'Neutral', 'Negative']
            counts = result.get('overall_sentiment_counts', {}) #gets overall sentiment percentages
            values = [counts.get(lbl, 0) for lbl in labels]

            #Generates pie chart for displaying the sentiment distribution
            fig = px.pie(
                names=labels,
                values=values,
                title=f"Overall Sentiment",
                color=labels,
                color_discrete_map={
                    'Positive': '#63FF70',
                    'Neutral': '#FFBF00',
                    'Negative': '#FF2A2A'
                },
            ) 
            fig.update_traces(textinfo='percent+label', textfont=dict(size=16, family="Arial Black"))
            fig.update_layout(margin=dict(t=50, b=50, l=50, r=50), paper_bgcolor = "#cbe5ff") 

            pros_summary = result.get('pros_summary', '') #Get's pros summary from the result
            cons_summary = result.get('cons_summary', '') #Get's cons summary from the result
            key_pros = result.get('key_pros', []) #Get's key pros summary from the result
            key_cons = result.get('key_cons', []) #Get's key cons summary from the result

            pros_items = [html.Li([html.B(p.get('title','')), f": {p.get('description','').strip().lower().capitalize()}"])
                         for p in key_pros] #Creates list of all pros with title and descriptions
            cons_items = [html.Li([html.B(c.get('title','')), f": {c.get('description','').strip().lower().capitalize()}"])
                         for c in key_cons] #Creates list of all pros with title and descriptions

            return html.Div([
                dbc.Row([
                    dbc.Col(dcc.Graph(figure=fig), width=6), #Displaying pie chart
                    dbc.Col(html.Div([
                        #Dsiplaying summaries for pros, cons, and key pros and cons with descriptions
                        html.H4("Pros", className="text-success"), #Green color
                        html.P(pros_summary),
                        html.H5("Key Pros", className="text-success"),
                        html.Ul(pros_items),
                        html.H4("Areas for Improvement", className="text-danger mt-4"), #Red color
                        html.P(cons_summary),
                        html.H5("Key Areas for Improvement", className="text-danger"),
                        html.Ul(cons_items),
                    ]), width=6)
                ], className="mb-4")
            ])

    @app.callback(
        Output("dept-content", "children"),
        Input("dept-dropdown", "value"),
        allow_duplicate=True
    )
    def update_dept_content(selected_dept):
        if not selected_dept:
            raise PreventUpdate #Prevents changes if nothing is selected

        db = firestore.client()
        bucket = storage.bucket()
        #Fetches latest report from firebase
        docs = (
            db.collection("reports")
              .order_by("timestamp", direction=firestore.Query.DESCENDING)
              .limit(1)
              .stream()
        )
        doc = next(docs)
        meta = doc.to_dict()
        blob = bucket.blob(meta["storage_path"])
        tmp = tempfile.NamedTemporaryFile(suffix=".csv", delete=False)
        blob.download_to_filename(tmp.name)
        df = pd.read_csv(tmp.name)

        cols = {c.lower(): c for c in df.columns}
        dept_col = next((cols[k] for k in cols if 'dept' in k or 'department' in k), None) #Find department column from the firestore storage csv associated with the report

        if dept_col:
            df = df[df[dept_col] == selected_dept] #Assigning only details of selected department records to df
            if df.empty:
                raise PreventUpdate
        else:
            raise PreventUpdate

        result = analyze_reviews(df, is_csv=False) #Sentiment Analysis
        counts = result.get('overall_sentiment_counts', {})
        labels = ['Positive', 'Neutral', 'Negative']
        values = [counts.get(l, 0) for l in labels] #Get's overall sentiment for that department

        fig = px.pie(
            names=labels,
            values=values,
            title=f"{selected_dept.capitalize()} Employee Sentiment",
            color=labels,
            color_discrete_map={
                'Positive': "#63FF70",
                'Neutral': '#FFBF00',
                'Negative': "#FF2A2A"
            }
        )
        fig.update_traces(textinfo='percent+label', textfont=dict(size=16, family="Arial Black"))
        fig.update_layout(margin=dict(t=50, b=50, l=50, r=50), paper_bgcolor = "#cbe5ff")

        #Saves pros and cons summary and key pros and cons with descriptions
        pros_summary = result.get('pros_summary', '')
        cons_summary = result.get('cons_summary', '')
        key_pros = result.get('key_pros', [])
        key_cons = result.get('key_cons', [])

        pros_items = [html.Li([html.B(p.get('title','')), f": {p.get('description','').strip().lower().capitalize()}"])
                      for p in key_pros]
        cons_items = [html.Li([html.B(c.get('title','')), f": {c.get('description','').strip().lower().capitalize()}"])
                      for c in key_cons]

        #Displays pros and cons summary and key pros and cons with descriptions and pie chart
        return html.Div([
            dbc.Row([
                dbc.Col(dcc.Graph(figure=fig), width=6),
                dbc.Col(html.Div([
                    html.H4("Pros", className="text-success"),
                    html.P(pros_summary),
                    html.H5("Key Pros", className="text-success"),
                    html.Ul(pros_items),
                    html.H4("Areas for Improvement", className="text-danger mt-4"),
                    html.P(cons_summary),
                    html.H5("Key Areas for Improvement", className="text-danger"),
                    html.Ul(cons_items),
                ]), width=6)
            ], className="mb-4")
        ])

    @app.callback(
        Output("status-content", "children"),
        Input("status-dropdown", "value"),
        allow_duplicate=True
    )
    def update_status_content(selected_status):
        if not selected_status:
            raise PreventUpdate #Prevents changes if nothing is selected

        db = firestore.client()
        bucket = storage.bucket()
        #Fetches latest report from firebase
        docs = (
            db.collection("reports")
              .order_by("timestamp", direction=firestore.Query.DESCENDING)
              .limit(1)
              .stream()
        )
        doc = next(docs)
        meta = doc.to_dict()
        blob = bucket.blob(meta["storage_path"])
        tmp = tempfile.NamedTemporaryFile(suffix=".csv", delete=False)
        blob.download_to_filename(tmp.name)
        df = pd.read_csv(tmp.name)

        cols = {c.lower(): c for c in df.columns}
        status_col = next((cols[k] for k in cols if 'status' in k), None) #Find job status column from the firestore storage csv associated with the report
        if status_col:
            df = df[df[status_col].astype(str).str.lower() == selected_status.lower()] #Assigning only details of current job status record to df
            if df.empty:
                raise PreventUpdate
        else:
            raise PreventUpdate

        result = analyze_reviews(df, is_csv=False) #Sentiment Analysis
        counts = result.get('overall_sentiment_counts', {})
        labels = ['Positive', 'Neutral', 'Negative']
        values = [counts.get(l, 0) for l in labels] #Get's overall sentiment for that job status
        fig = px.pie(
            names=labels,
            values=values,
            title=f"{selected_status.capitalize()} Employee Sentiment",
            color=labels,
            color_discrete_map={
                'Positive': "#63FF70",
                'Neutral': '#FFBF00',
                'Negative': "#FF2A2A"
            }
        )
        fig.update_traces(textinfo='percent+label', textfont=dict(size=26, family="Arial Black"))
        fig.update_layout(margin=dict(t=50, b=50, l=50, r=50), paper_bgcolor = "#cbe5ff") #Generates pie chart of sentiment distribution
        
        #Saves pros and cons summary and key pros and cons with descriptions
        pros_summary = result.get('pros_summary', '') 
        cons_summary = result.get('cons_summary', '') 
        key_pros = result.get('key_pros', [])
        key_cons = result.get('key_cons', [])

        pros_items = [html.Li([html.B(p.get('title','')), f": {p.get('description','').strip().lower().capitalize()}"])
                      for p in key_pros]
        cons_items = [html.Li([html.B(c.get('title','')), f": {c.get('description','').strip().lower().capitalize()}"])
                      for c in key_cons]

        #Displays pros and cons summary and key pros and cons with descriptions and pie chart
        return html.Div([
            dbc.Row([
                dbc.Col(dcc.Graph(figure=fig), width=6),
                dbc.Col(html.Div([
                    html.H4("Pros", className="text-success"),
                    html.P(pros_summary),
                    html.H5("Key Pros", className="text-success"),
                    html.Ul(pros_items),
                    html.H4("Areas for Improvement", className="text-danger mt-4"),
                    html.P(cons_summary),
                    html.H5("Key Areas for Improvement", className="text-danger"),
                    html.Ul(cons_items),
                ]), width=6)
            ], className="mb-4")
        ])

    @app.callback(
        Output("download-pdf", "data"),
        Input("download-btn", "n_clicks"),
        prevent_initial_call=True,
        allow_duplicate=True
    )
    def download_pdf(n):
        #Repeats previous steps to get details of the report including pros and cons summary and key pros and cons with descriptions and sentiment distribution
        db = firestore.client()
        bucket = storage.bucket()
        docs = (
            db.collection("reports")
              .order_by("timestamp", direction=firestore.Query.DESCENDING)
              .limit(1)
              .stream()
        )
        doc = next(docs)
        meta = doc.to_dict()
        doc_ref = doc.reference

        blob = bucket.blob(meta["storage_path"])
        tmp = tempfile.NamedTemporaryFile(suffix=".csv", delete=False)
        blob.download_to_filename(tmp.name)
        df = pd.read_csv(tmp.name)

        result_general = analyze_reviews(tmp.name)
        counts = result_general.get('overall_sentiment_counts', {})
        pros_summary = result_general.get('pros_summary', '')
        cons_summary = result_general.get('cons_summary', '')
        key_pros = result_general.get('key_pros', [])
        key_cons = result_general.get('key_cons', [])

        #Generating pie chart for overall sentiment
        labels = ['Positive', 'Neutral', 'Negative']
        values = [counts.get(l, 0) for l in labels] # Fetches values for pie chart
        colors = ['#63FF70', '#FFBF00', '#FF2A2A']  # hex code for amber inserted
        plt.figure(figsize=(6,6))
        plt.pie(values, labels=labels, autopct='%1.1f%%', colors=colors, startangle=90)
        plt.title("Overall Sentiment") #Piechart title
        img_general = tempfile.NamedTemporaryFile(suffix=".png", delete=False) #temporary file for generating the pie chart
        plt.savefig(img_general.name, bbox_inches='tight') #Saves the piechart 
        plt.close()

        #Prepares default style, title, subtitle, and body styles
        styles = getSampleStyleSheet()
        title_style = styles['Heading1']
        subtitle_style = styles['Heading2']
        body_style = styles['BodyText']

        story = [] #Starts dictionary where pdf will be generated onto
        story.append(Paragraph("Sentiment Analysis Report", title_style)) #Adds text sentiment analysis
        date_str = datetime.date.today().strftime('%B %d, %Y')
        story.append(Paragraph(f"Generated on {date_str}", subtitle_style)) #Adds date and timestamp
        story.append(Spacer(1, 12)) #Spacing between elements with format of - horizontal, vertical 

        story.append(Image(img_general.name, width=400, height=400)) #Adds an image that is the pie chart
        story.append(Spacer(1, 12))

        story.append(Paragraph("Pros", subtitle_style)) #Pros Header
        story.append(Paragraph(pros_summary, body_style)) #Pros Summary title added
        #Loops through the list of pros in key_pros and add corresponding descriptions as a bullet point style list to the pdf
        for p in key_pros:
            title = p.get('title', '') 
            desc = p.get('description', '').strip().lower().capitalize()
            story.append(ListFlowable([Paragraph(f"<b>{title}</b>: {desc}", body_style)], bulletType='bullet', leftIndent=20))
        story.append(Spacer(1, 6))
        story.append(Paragraph("Areas for Improvement", subtitle_style)) #Repeats steps for cons
        story.append(Paragraph(cons_summary, body_style))
        for c in key_cons:
            title = c.get('title', '')
            desc = c.get('description', '').strip().lower().capitalize()
            story.append(ListFlowable([Paragraph(f"<b>{title}</b>: {desc}", body_style)], bulletType='bullet', leftIndent=20))

        # Repeats steps for adding overall sentiment for department sentiment, below overall sentiment details with same steps as report generation
        dept_cols = [c for c in df.columns if 'dept' in c.lower() or 'department' in c.lower()] 
        if dept_cols:
            dept_col = dept_cols[0]
            departments = sorted(df[dept_col].dropna().unique())
            for dept in departments:
                df_dept = df[df[dept_col] == dept]
                if df_dept.empty:
                    continue
                result_dept = analyze_reviews(df_dept, is_csv=False)
                counts_d = result_dept.get('overall_sentiment_counts', {})
                pros_sum_d = result_dept.get('pros_summary', '')
                cons_sum_d = result_dept.get('cons_summary', '')
                key_pros_d = result_dept.get('key_pros', [])
                key_cons_d = result_dept.get('key_cons', [])

                values_d = [counts_d.get(l, 0) for l in labels]
                plt.figure(figsize=(6,6))
                plt.pie(values_d, labels=labels, autopct='%1.1f%%', colors=colors, startangle=90)
                plt.title(f"{dept} Sentiment")
                img_dept = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
                plt.savefig(img_dept.name, bbox_inches='tight')
                plt.close()

                story.append(PageBreak())
                story.append(Paragraph(f"Department: {dept}", subtitle_style))
                story.append(Spacer(1, 12))
                story.append(Image(img_dept.name, width=400, height=400))
                story.append(Spacer(1, 12))

                story.append(Paragraph("Pros", subtitle_style))
                story.append(Paragraph(pros_sum_d, body_style))
                for p in key_pros_d:
                    title = p.get('title', '')
                    desc = p.get('description', '').strip().lower().capitalize()
                    story.append(ListFlowable([Paragraph(f"<b>{title}</b>: {desc}", body_style)], bulletType='bullet', leftIndent=20))
                story.append(Spacer(1, 6))
                story.append(Paragraph("Areas for Improvement", subtitle_style))
                story.append(Paragraph(cons_sum_d, body_style))
                for c in key_cons_d:
                    title = c.get('title', '')
                    desc = c.get('description', '').strip().lower().capitalize()
                    story.append(ListFlowable([Paragraph(f"<b>{title}</b>: {desc}", body_style)], bulletType='bullet', leftIndent=20))

        # Repeats steps for adding overall sentiment for job status sentiment, below department based sentiment details with same steps as report generation
        status_cols = [c for c in df.columns if 'status' in c.lower()]
        if status_cols:
            status_col = status_cols[0]
            statuses = sorted(df[status_col].dropna().unique())
            for status in statuses:
                df_stat = df[df[status_col] == status]
                if df_stat.empty:
                    continue
                result_stat = analyze_reviews(df_stat, is_csv=False)
                counts_s = result_stat.get('overall_sentiment_counts', {})
                pros_sum_s = result_stat.get('pros_summary', '')
                cons_sum_s = result_stat.get('cons_summary', '')
                key_pros_s = result_stat.get('key_pros', [])
                key_cons_s = result_stat.get('key_cons', [])

                values_s = [counts_s.get(l, 0) for l in labels]
                plt.figure(figsize=(6,6))
                plt.pie(values_s, labels=labels, autopct='%1.1f%%', colors=colors, startangle=90)
                plt.title(f"{status} Employee Sentiment")
                img_stat = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
                plt.savefig(img_stat.name, bbox_inches='tight')
                plt.close()

                story.append(PageBreak())
                story.append(Paragraph(f"Status: {status}", subtitle_style))
                story.append(Spacer(1, 12))
                story.append(Image(img_stat.name, width=400, height=400))
                story.append(Spacer(1, 12))

                story.append(Paragraph("Pros", subtitle_style))
                story.append(Paragraph(pros_sum_s, body_style))
                for p in key_pros_s:
                    title = p.get('title', '')
                    desc = p.get('description', '').strip().lower().capitalize()
                    story.append(ListFlowable([Paragraph(f"<b>{title}</b>: {desc}", body_style)], bulletType='bullet', leftIndent=20))
                story.append(Spacer(1, 6))
                story.append(Paragraph("Areas for Improvement", subtitle_style))
                story.append(Paragraph(cons_sum_s, body_style))
                for c in key_cons_s:
                    title = c.get('title', '')
                    desc = c.get('description', '').strip().lower().capitalize()
                    story.append(ListFlowable([Paragraph(f"<b>{title}</b>: {desc}", body_style)], bulletType='bullet', leftIndent=20))

        
        
        buffer = BytesIO() #Creates a buffer variable to temporarily store the pdf for building with Bytes datatype to store the file
        #Variable is a bytes variable for easily passing onto browser for enabling download
        doc_pdf = SimpleDocTemplate(buffer, pagesize=letter) #Uses reportlabs to create a pdf document template and store in doc_pdf with bytes version in buffer
        doc_pdf.build(story) #Build the story dictionary into doc_pdf to buld the pdf
        pdf_bytes = buffer.getvalue() #Stores the details of the pdf in byte form from buffer into pdf_bytes

        csv_name = meta["storage_path"].split("/")[-1] #Finds csv name from filepath in firestore storage
        base_name = csv_name.rsplit(".", 1)[0] #Finds basename of the csv
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S") #Generates timestamp
        pdf_name = f"{base_name}_{timestamp}.pdf" #Stores pdf name by combining base name and timestamp
        pdf_path = f"reports/{pdf_name}" #Defines filepath of the pdf in the reports collection in firebase

        blob_pdf = bucket.blob(pdf_path) #Stores details of the firestore storage handle where te file should be sotres
        blob_pdf.upload_from_string(pdf_bytes, content_type='application/pdf') #Uploads the bytes information of the pdf to that firestore storage handle
        #The content type also defined for the browser to know it is a df 
        doc_ref.update({"pdf_path": pdf_path}) #Updates the file path with the firestorage storage handle

        return dcc.send_bytes(pdf_bytes, filename=pdf_name) #returns the bytes version of the pdf to dash to download via the browser

    #Repeats pdf generation steps for upload to firestore storage immediately when the report page is loaded
    @app.callback(
        [
            Output("upload-toast", "is_open"), #Checks if the upload bar is hidden or visible
            Output("upload-progress", "style")  # Progress bar for pdf upload 
        ],
        Input("pdf-upload-interval", "n_intervals")
    )
    def upload_pdf_on_load(n):
        if not n:
            raise PreventUpdate

        db = firestore.client()
        bucket = storage.bucket()
        docs = (
            db.collection("reports")
              .order_by("timestamp", direction=firestore.Query.DESCENDING)
              .limit(1)
              .stream()
        )
        doc = next(docs)
        meta = doc.to_dict()
        doc_ref = doc.reference

        # download the latest CSV
        blob = bucket.blob(meta["storage_path"])
        tmp = tempfile.NamedTemporaryFile(suffix=".csv", delete=False)
        blob.download_to_filename(tmp.name)
        df = pd.read_csv(tmp.name)

        # analyze overall
        result_general = analyze_reviews(tmp.name)
        counts = result_general.get('overall_sentiment_counts', {})
        pros_summary = result_general.get('pros_summary', '')
        cons_summary = result_general.get('cons_summary', '')
        key_pros = result_general.get('key_pros', [])
        key_cons = result_general.get('key_cons', [])

        # generate pie chart image for general
        labels = ['Positive', 'Neutral', 'Negative']
        values = [counts.get(l, 0) for l in labels]
        colors = ['#63FF70', '#FFBF00', '#FF2A2A']  # Colors for the pie chart - hex code for amber
        plt.figure(figsize=(6,6))
        plt.pie(values, labels=labels, autopct='%1.1f%%', colors=colors, startangle=90)
        plt.title("Overall Sentiment")
        img_general = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        plt.savefig(img_general.name, bbox_inches='tight')
        plt.close()

        # prepare PDF content
        styles = getSampleStyleSheet()
        title_style = styles['Heading1']
        subtitle_style = styles['Heading2']
        body_style = styles['BodyText']

        story = []
        story.append(Paragraph("Sentiment Analysis Report", title_style))
        date_str = datetime.date.today().strftime('%B %d, %Y')
        story.append(Paragraph(f"Generated on {date_str}", subtitle_style))
        story.append(Spacer(1, 12))

        story.append(Image(img_general.name, width=400, height=400))
        story.append(Spacer(1, 12))

        story.append(Paragraph("Pros", subtitle_style))
        story.append(Paragraph(pros_summary, body_style))
        for p in key_pros:
            title = p.get('title', '')
            desc = p.get('description', '').strip().lower().capitalize()
            story.append(ListFlowable([Paragraph(f"<b>{title}</b>: {desc}", body_style)], bulletType='bullet', leftIndent=20))
        story.append(Spacer(1, 6))
        story.append(Paragraph("Areas for Improvement", subtitle_style))
        story.append(Paragraph(cons_summary, body_style))
        for c in key_cons:
            title = c.get('title', '')
            desc = c.get('description', '').strip().lower().capitalize()
            story.append(ListFlowable([Paragraph(f"<b>{title}</b>: {desc}", body_style)], bulletType='bullet', leftIndent=20))

        # Department analysis
        dept_cols = [c for c in df.columns if 'dept' in c.lower() or 'department' in c.lower()]
        if dept_cols:
            dept_col = dept_cols[0]
            departments = sorted(df[dept_col].dropna().unique())
            for dept in departments:
                df_dept = df[df[dept_col] == dept]
                if df_dept.empty:
                    continue
                result_dept = analyze_reviews(df_dept, is_csv=False)
                counts_d = result_dept.get('overall_sentiment_counts', {})
                pros_sum_d = result_dept.get('pros_summary', '')
                cons_sum_d = result_dept.get('cons_summary', '')
                key_pros_d = result_dept.get('key_pros', [])
                key_cons_d = result_dept.get('key_cons', [])

                values_d = [counts_d.get(l, 0) for l in labels]
                plt.figure(figsize=(6,6))
                plt.pie(values_d, labels=labels, autopct='%1.1f%%', colors=colors, startangle=90)
                plt.title(f"{dept} Sentiment")
                img_dept = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
                plt.savefig(img_dept.name, bbox_inches='tight')
                plt.close()

                story.append(PageBreak())
                story.append(Paragraph(f"Department: {dept}", subtitle_style))
                story.append(Spacer(1, 12))
                story.append(Image(img_dept.name, width=400, height=400))
                story.append(Spacer(1, 12))

                story.append(Paragraph("Pros", subtitle_style))
                story.append(Paragraph(pros_sum_d, body_style))
                for p in key_pros_d:
                    title = p.get('title', '')
                    desc = p.get('description', '').strip().lower().capitalize()
                    story.append(ListFlowable([Paragraph(f"<b>{title}</b>: {desc}", body_style)], bulletType='bullet', leftIndent=20))
                story.append(Spacer(1, 6))
                story.append(Paragraph("Areas for Improvement", subtitle_style))
                story.append(Paragraph(cons_sum_d, body_style))
                for c in key_cons_d:
                    title = c.get('title', '')
                    desc = c.get('description', '').strip().lower().capitalize()
                    story.append(ListFlowable([Paragraph(f"<b>{title}</b>: {desc}", body_style)], bulletType='bullet', leftIndent=20))

        # Employment status analysis
        status_cols = [c for c in df.columns if 'status' in c.lower()]
        if status_cols:
            status_col = status_cols[0]
            statuses = sorted(df[status_col].dropna().unique())
            for status in statuses:
                df_stat = df[df[status_col] == status]
                if df_stat.empty:
                    continue
                result_stat = analyze_reviews(df_stat, is_csv=False)
                counts_s = result_stat.get('overall_sentiment_counts', {})
                pros_sum_s = result_stat.get('pros_summary', '')
                cons_sum_s = result_stat.get('cons_summary', '')
                key_pros_s = result_stat.get('key_pros', [])
                key_cons_s = result_stat.get('key_cons', [])

                values_s = [counts_s.get(l, 0) for l in labels]
                plt.figure(figsize=(6,6))
                plt.pie(values_s, labels=labels, autopct='%1.1f%%', colors=colors, startangle=90)
                plt.title(f"{status} Employee Sentiment")
                img_stat = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
                plt.savefig(img_stat.name, bbox_inches='tight')
                plt.close()

                story.append(PageBreak())
                story.append(Paragraph(f"Status: {status}", subtitle_style))
                story.append(Spacer(1, 12))
                story.append(Image(img_stat.name, width=400, height=400))
                story.append(Spacer(1, 12))

                story.append(Paragraph("Pros", subtitle_style))
                story.append(Paragraph(pros_sum_s, body_style))
                for p in key_pros_s:
                    title = p.get('title', '')
                    desc = p.get('description', '').strip().lower().capitalize()
                    story.append(ListFlowable([Paragraph(f"<b>{title}</b>: {desc}", body_style)], bulletType='bullet', leftIndent=20))
                story.append(Spacer(1, 6))
                story.append(Paragraph("Areas for Improvement", subtitle_style))
                story.append(Paragraph(cons_sum_s, body_style))
                for c in key_cons_s:
                    title = c.get('title', '')
                    desc = c.get('description', '').strip().lower().capitalize()
                    story.append(ListFlowable([Paragraph(f"<b>{title}</b>: {desc}", body_style)], bulletType='bullet', leftIndent=20))

        # build PDF
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        doc.build(story)
        pdf_bytes = buffer.getvalue()

        csv_name = meta["storage_path"].split("/")[-1]
        base_name = csv_name.rsplit(".", 1)[0]
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        pdf_name = f"{base_name}_{timestamp}.pdf"
        pdf_path = f"reports/{pdf_name}"

        blob_pdf = bucket.blob(pdf_path)
        blob_pdf.upload_from_string(pdf_bytes, content_type='application/pdf')
        doc_ref.update({"pdf_path": pdf_path})

        return True, {"display": "none"}  # Displays the page
