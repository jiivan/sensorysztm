#!/bin/bash

./run.bash $1 && cd tmp && pdflatex *.tex && mv *.pdf ../output && cd .. && rm tmp/*
