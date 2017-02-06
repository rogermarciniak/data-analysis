import hashlib
import json
import operator
import os
import string
from collections import Counter

import jinja2
from flask import (Flask, flash, redirect, render_template, request,
                   send_from_directory, session, url_for)
from pymongo import MongoClient
from werkzeug.utils import secure_filename

'''
Author: Roger Marciniak
Student#: C00169733
Program: WordGame
'''


# TODO: OPTIONAL: add comments and split app layers (place code in functions)

UPLOAD_FOLDER = '/home/roger/Desktop/data_analysis_project/userfiles'
ALLOWED_EXTENSIONS = set(['txt'])


app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
# maximum file size will be 16MB
# app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.add_template_global(list, name='list')
app.add_template_global(int, name='int')


# prepares db
client = MongoClient()
db = client.datanDB
analyses = db.analyses  # token col


# This function tokenizes the file provided by the user
def tokenize(fileToTokenize):
    file = open(fileToTokenize, 'r', encoding='utf-8', errors='replace')
    tokens = []
    for line in file:
        # convert to lowercase (per line is more efficient than per word)
        lineLower = line.lower()
        # gets rid of '\n' characters which mess up tokenization
        oneLine = lineLower.replace('\n', "")

        # populates a list of tokens & strips punctuation
        # but allows hyphenated words & apostrophes if inside a word
        tokens.extend([word.strip(string.punctuation)
                       for word in oneLine.split(" ")])

    tokens = list(filter(None, tokens))
    return tokens


# This function produces a SHA1 hash for the file provided by the user
def getSHA(fileToHash):
    # blocksize is set in case the file is very large
    BLOCKSIZE = 65536
    hasher = hashlib.sha1()
    # 'rb' ensures that we can hash any file, not only a text file
    # for possible future use
    with open(fileToHash, 'rb') as afile:
        buf = afile.read(BLOCKSIZE)
        while len(buf) > 0:
            hasher.update(buf)
            buf = afile.read(BLOCKSIZE)

    print(hasher.hexdigest())
    return hasher.hexdigest()


# This function counts the occurrences of the words provided by the user
def countOccurrences(tokens):
    # tokens and count in {session['token'] : occurrences} format
    tokenOcc = dict(Counter(tokens))
    return tokenOcc

# This function checks if a document with specified hash exists


def exists(hashed):
    exist = analyses.find_one({'filehash': hashed})
    return exist

# This function loads the associations JSON file


def loadJSONfile():
    with open('ea-thesaurus-lower.json') as normsf:
        norms = json.load(normsf)
    return norms


# This function checks if the file has the right extension
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# displays the file (not needed)
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'],
                               filename)


@app.route('/', methods=['GET', 'POST'])
def basic_analysis():
    # uploadfile.html rendered unless method is POST, then basicanalysis.html
    if request.method == 'POST':
        # check if the post request has the file part
        if 'file' not in request.files:
            return redirect(request.url)

        file = request.files['file']

        # if user does not select file, browser also
    # submits an empty part without filename
        if file.filename == '':
            flash('Error: No file selected!')
            return redirect(request.url)

        if file and allowed_file(file.filename):
            session['filename'] = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], session['filename']))
            # setting the filepath to the uploaded file
            session['filepath'] = os.path.join(UPLOAD_FOLDER, session['filename'])
            session['fileSHA'] = getSHA(session['filepath'])  # file hash
            if exists(session['fileSHA']):
                flash("Error: File was previously analysed! Go to 'Previous Analyses'!")
                return render_template('uploadfile.html')
            else:
                session['tokenList'] = tokenize(session['filepath'])  # tokens
                # list of unique {token, occurrences} dicts
                session['uniqueTokens'] = countOccurrences(session['tokenList'])
                # initializing lists
                session['wordsFound'] = []
                session['wordFreq'] = []
                session['wordAssocs'] = []
                session['wordsNFound'] = []
                session['wordsNFFreq'] = []

                # loads JSON file
                assocs = loadJSONfile()

                # checks if user words exist in JSON file and populates lists with data
                for k, v in list(session['uniqueTokens'].items()):
                    if k in assocs.keys():
                        session['ass'] = assocs[k][:3]  # first 3 associatons
                        session['wordsFound'] += [k]  # list of words
                        session['wordFreq'] += [v]  # list of ints
                        session['wordAssocs'] += [session['ass']]  # list of lists of dicts
                    else:
                        session['wordsNFound'] += [k]  # list of words
                        session['wordsNFFreq'] += [v]  # list of ints
                wrds = list(zip(session['wordsFound'],
                                session['wordFreq'],
                                session['wordAssocs']))
                wrds.sort(key=operator.itemgetter(0))  # sort by words
                wrds.sort(key=operator.itemgetter(1), reverse=True)  # upsort by frequency
                print(session['wordsFound'])
                print(type(session['wordsFound']))
                print(session['wordFreq'])
                print(type(session['wordFreq']))
                print(session['wordAssocs'])
                print(type(session['wordAssocs']))
                wrdsNF = list(zip(session['wordsNFound'], session['wordsNFFreq']))
                wrdsNF.sort(key=operator.itemgetter(0))
                wrdsNF.sort(key=operator.itemgetter(1), reverse=True)
                return render_template('basicanalysis.html',
                                       wrds=wrds,
                                       wrdsNF=wrdsNF)
    return render_template('uploadfile.html')


@app.route('/advanced', methods=['GET', 'POST'])
def advanced_analysis():
    fileN = session.get('filename')
    fileSHA = session.get('fileSHA')
    wordsFound = session.get('wordsFound')
    wordFreq = session.get('wordFreq')
    wordAssocs = session.get('wordAssocs')
    ass_score = int(request.form.get('choice'))
    wordRanks = []
    rankTrace = []
    # <--here (TypeError: zip argument #1 must support iteration)
    data = list(zip(wordsFound, wordFreq, wordAssocs))
    for word, wordfreq, asso in data:
        # because .values() returns a view object, it needs to be converted to list
        associationSc = int(list(asso[ass_score].values())[0])
        currentRank = wordfreq * associationSc
        wordRanks += [wordfreq * associationSc]
        rankTrace += ['{} * {}'.format(wordfreq, associationSc)]

        session['token'] = {"file": fileN,
                            "filehash": fileSHA,
                            "token": word,
                            "rank": currentRank,
                            "frequency": wordfreq,
                            "firstassoc": asso[0],  # top association
                            "secondassoc": asso[1],  # 2nd best association
                            "thirdassoc": asso[2],  # 3rd best association
                            "user_choice": ass_score,  # first|second|third association
                            "association_sc": associationSc}  # association's score
        result = analyses.update(session['token'], session['token'], upsert=True)

    items = list(zip(wordsFound, wordRanks, rankTrace))
    items.sort(key=operator.itemgetter(0))
    items.sort(key=operator.itemgetter(1), reverse=True)
    return render_template('advancedanalysis.html',
                           choice=ass_score,
                           items=items)


@app.route('/pastanalyses', methods=['GET', 'POST'])
def past_analyses():
    shaList = analyses.distinct('filehash')
    docs = []
    for hsh in shaList:
        doc = analyses.find_one({'filehash': hsh})
        docs.append(doc)
    return render_template('pastanalyses.html',
                           docs=docs)


@app.route('/pastanalysis', methods=['GET', 'POST'])
def past_analysis():
    fileHash = request.form.get('filehash')
    result = analyses.find({'filehash': fileHash})
    docsFound = []
    for doc in result:
        docsFound.append(doc)
    docsFound = sorted(docsFound, key=operator.itemgetter('token'))
    docsFound = sorted(docsFound, key=operator.itemgetter('rank'), reverse=True)
    return render_template('pastanalysis.html', docs=docsFound)


@app.errorhandler(404)
def fourOhFour(error):
    return '404: You have wandered too far young adventurer!'


app.secret_key = os.urandom(32)


if __name__ == '__main__':
    app.run(debug=True)
