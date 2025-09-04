#Importing Libraries
import os
import re
import string
import pandas as pd
from collections import Counter
from bs4 import BeautifulSoup
import google.generativeai as genai

GOOGLE_API_KEY = "AIzaSyBiJ77_YHWvYsYFbdunTVYQTKodndf0SkM" #Declaring gemini API Key
genai.configure(api_key=GOOGLE_API_KEY) #Configuring gemini
model = genai.GenerativeModel("gemini-1.5-flash") #Setting type of model
chat = model.start_chat() #Creating new gemini chat


def clean_html_text(html_text: str) -> str: #Converts html to string
    if not isinstance(html_text, str):
        return '' #If not html, returns null string
    return BeautifulSoup(html_text, 'lxml').get_text(separator=' ', strip=True)

def call_gemini(prompt: str, max_output_tokens: int = 150) -> str:
    #Setting call gemini function, reiterating model
    response = model.generate_content(prompt) #Asks gemini the prompt and stores it's response
    return response.text.strip() #Returns response without trailing punctuation

def analyze_reviews(data_source, is_csv: bool = True) -> dict:
    #is_csv is false for pandas dataframe and true in the case of CSVs
    df = pd.read_csv(data_source) if is_csv else data_source.copy() #If it is a csv, creates dataframe for the csv, else copies the exisitng dataframe
    
    cols = {c.lower(): c for c in df.columns} #Lower case dictionary of all columns
    #Identifying relevant columns in the dataframe and storing them in variables
    
    rating_col = next((cols[k] for k in cols if 'rating' in k), None)
    pros_col   = next((cols[k] for k in cols if 'pros' in k), None)
    cons_col   = next((cols[k] for k in cols if 'cons' in k), None)
    comm_col   = next((cols[k] for k in cols if 'comment' in k or 'review' in k), None)
    title_col  = next((cols[k] for k in cols if 'job' in k or 'role' in k or 'position' in k), None)
    status_col = next((cols[k] for k in cols if 'status' in k or 'employment' in k), None)
    dept_col   = next((cols[k] for k in cols if 'department' in k), None)

    if not rating_col:
        raise ValueError("No rating column found.") #If no rating found
    if not ((pros_col and cons_col) or comm_col):
        raise ValueError("Need pros/cons columns or review comments column.") #If no pros/cons column or review text found

    for col in (pros_col, cons_col, comm_col): #Cleaning dataframe
        if col:
            df[col] = df[col].astype(str).apply(clean_html_text) #Removes any html elements from the columns

    df = df.dropna(subset=[rating_col]) #Removes records if the rating is null
    df[rating_col] = pd.to_numeric(df[rating_col], errors='coerce') #Converts ratings to integers
    df = df.dropna(subset=[rating_col]) #Repeats null record removal

    df['Sentiment'] = df[rating_col].apply(lambda r: 'Positive' if r >= 4 else ('Neutral' if r == 3 else 'Negative')) #Classifies sentiment based on rating and stores in new sentiment column

    #Classifying employment status
    def classify_status(x):
        x = str(x).lower()
        if re.search(r'\b(current|present|active)\b', x): #different possible terms for current
            return 'Current'
        if re.search(r'\b(former|past|previous|ex)\b', x): #different possible terms for former
            return 'Former'
        return 'Unknown' #If no mention of status is found
    df['EmpStatus'] = df[status_col].apply(classify_status) if status_col else 'Unknown' #Classifies employment status in a new column 

    #Department classification
    if dept_col: #If there is a department column
        df['Department'] = df[dept_col].astype(str).replace('', 'Other')
    else: #If there is a job title column and no department column
        def map_dept(title):
            t = str(title).lower()
            if 'hr' in t or 'human resources' in t:
                return 'HR'
            if any(k in t for k in ['it','engineer','software','developer','tech']):
                return 'IT'
            if 'admin' in t or 'assistant' in t or 'office' in t:
                return 'Admin'
            if 'sales' in t or 'account' in t:
                return 'Sales'
            if 'marketing' in t:
                return 'Marketing'
            if 'finance' in t or 'accounting' in t:
                return 'Finance'
            return 'Other'
        df['Department'] = df[title_col].apply(map_dept) if title_col else 'Other' #Adds department column that stores classification

    #Calculate overall sentiment and sentiment percentage distribution
    total_reviews = len(df) #Number of reviews
    counts = df['Sentiment'].value_counts().to_dict() #Converts sentiment values to dictionary
    overall_counts = {s: counts.get(s, 0) for s in ['Positive', 'Neutral', 'Negative']} #Get's total sentiment count for each sentiment calssification
    overall_percentages = {
        s: (overall_counts[s] / total_reviews * 100 if total_reviews else 0)
        for s in overall_counts
    } #calculates percentage of reviews having a sentiment

    #Gets number of reviews of each sentiment classification and total reviews for each department and each job tenure
    dept_sentiment = {
        d: {
            'Positive': g['Sentiment'].value_counts().get('Positive', 0),
            'Neutral':  g['Sentiment'].value_counts().get('Neutral', 0),
            'Negative': g['Sentiment'].value_counts().get('Negative', 0),
            'TotalReviews': len(g)
        }
        for d, g in df.groupby('Department')
    }
    status_sentiment = {
        s: {
            'Positive': g['Sentiment'].value_counts().get('Positive', 0),
            'Neutral':  g['Sentiment'].value_counts().get('Neutral', 0),
            'Negative': g['Sentiment'].value_counts().get('Negative', 0),
            'TotalReviews': len(g)
        }
        for s, g in df.groupby('EmpStatus')
    }

    #Combines all pros and cons, removing null values
    pros_text = " ".join(df[pros_col].dropna()) if pros_col else ""
    cons_text = " ".join(df[cons_col].dropna()) if cons_col else ""
    if comm_col:
        pros_text += " " + " ".join(df[df['Sentiment']=='Positive'][comm_col].dropna()) #Pros are with positive sentiment
        cons_text += " " + " ".join(df[df['Sentiment']=='Negative'][comm_col].dropna()) #Cons are with negative sentiment

    #Extracting common key words
    def get_top_words(text, n=5):
        txt = clean_html_text(text).lower()
        txt = txt.translate(str.maketrans('', '', string.punctuation)) #removes punctuation
        words = [w for w, _ in Counter(txt.split()).most_common(200)] #Counter library used to keep count of number of most common words found
        stop = {
            "and","the","for","with","are","not","but","all","was","were","have","has","had",
            "this","that","those","these","from","too","out","they","you","your","our","their",
            "about","into","over","under","few","many","most","other","some","any","each","much",
            "more","well","lot","lots","make","makes","very","just","really","every","also",
            "can","could","would","should","use","used","work","working"
        } #Conjunctions, transitions, pronouns and other common words not related to the workplace review
        return [w for w in words if w.isalpha() and w not in stop][:n] #Slices out and returns top n number of words

    top_pros = get_top_words(pros_text, n=5) #Takes first 5 pros - 5 most common
    top_cons = get_top_words(cons_text, n=5) #Takes first 5 pros - 5 most common

    def list_to_text(lst):
        #Converts list of python words to a sentence
        if not lst:
            return ""
        if len(lst) == 1:
            return lst[0]
        if len(lst) == 2:
            return f"{lst[0]} and {lst[1]}"
        return ", ".join(lst[:-1]) + f", and {lst[-1]}"

    #Generates summary for pros from the reviews using gemini
    if top_pros:
        prompt = (
            f"Employees often mention {list_to_text([w.capitalize() for w in top_pros])} as positive aspects of their workplace. "
            "In about 60-70 words, write a detailed paragraph explaining the overall impact of these strengths on employee wellbeing and maintiaining a strong workplace culture."
        )
        pros_summary = call_gemini(prompt, max_output_tokens=100) #Calls gemini to answer the prompt and stores response
    else:
        pros_summary = "No positive aspects were highlighted."

    #Generates summary for cons from the reviews using gemini
    if top_cons:
        prompt = (
            f"Employees often mention {list_to_text([w.capitalize() for w in top_cons])} as negative aspects of their workplace. "
            "In about 60-70 words, write a detailed paragraph explaining why these concerns are important to fix and how a fix could help improve employee wellbeing."
        )
        cons_summary = call_gemini(prompt, max_output_tokens=100)
    else:
        cons_summary = "No negative aspects were highlighted."

    #Generating detailed sentences for the top 5 pros
    key_pros = []
    for kw in top_pros:
        title = kw.capitalize()
        prompt = f"In one sentence (about 25 words), explain why '{title}' helps benefit employees and their wellbeing while also explaining how it links to the workpalce directly."
        desc = call_gemini(prompt, max_output_tokens=50).strip() 
        desc = desc + '.' if desc else '' #Adds punctuation at the end
        key_pros.append({"title": title, "description": desc}) #Adds the key pro and its description to the list of pros

    #Generating detailed sentences for the top 5 pros
    key_cons = []
    for kw in top_cons:
        title = kw.capitalize()
        prompt = f"In one sentence (about 25 words), explain why '{title}' is a concern for employees and their wellbeing while also explaining how it links to the workpalce directly."
        desc = call_gemini(prompt, max_output_tokens=50).strip()
        desc = desc + '.' if desc else ''
        key_cons.append({"title": title, "description": desc}) #Adds the key con and its description to the list of cons

    #Returning all analysis results in a dictionary
    return {
        "overall_sentiment_counts": overall_counts,
        "overall_sentiment_percentages": overall_percentages,
        "department_sentiment": dept_sentiment,
        "status_sentiment": status_sentiment,
        "pros_summary": pros_summary,
        "cons_summary": cons_summary,
        "key_pros": key_pros,
        "key_cons": key_cons
    }
