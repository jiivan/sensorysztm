#!/bin/bash

./run.bash && cd tmp && pdflatex *.tex && mv *.pdf ../output && cd .. && rm tmp/*
