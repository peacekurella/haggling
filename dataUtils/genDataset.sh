#!/bin/bash

read -e -p $'Enable Normalization (Y/N) : \n' -i "Y" PREP
python preprocessing.py
rm -r ../input
if [ $PREP = $"Y" ];then
  python normalize.py
  python createRecords.py --train ../normalized/train  --test ../normalized/test
  rm -r ../normalized
  rm -r ../preprocessed
else
  python createRecords.py --input ../preprocessed
  rm -r ../preprocessed
fi
mkdir ../inference
mkdir ../convOut