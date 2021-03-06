# -*- coding: utf-8 -*-
"""name_Entity .ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1c5V_hlXzhrVnHaaV3nfY0HIZ6UJa32zg
"""

import os
try:
  !pip install transformers
  if not os.path.exists('/content/sample_submission.csv') and not os.path.exists('/content/train.csv.zip') and not os.path.exists('/content/test.csv'):
    ! mkdir ~/.kaggle
    ! mv kaggle.json ~/.kaggle/
    ! chmod 600 ~/.kaggle/kaggle.json
    !kaggle datasets download -d abhinavwalia95/entity-annotated-corpus
except:
  pass

from google.colab import files

def data_directory():
  try:
    if not os.path.exists('/content/Name_Entity'):
      !mkdir Name_Entity
      !mkdir /content/Name_Entity/train_data
      !unzip /content/entity-annotated-corpus.zip -d /content/Name_Entity/train_data

  except:
    pass

  return {
      'train_data_path':'/content/Name_Entity/train_data/ner_dataset.csv',
    }

import pandas as pd
import numpy as np
import config
import torch
from tqdm import tqdm
import torch.nn as nn
import joblib
import transformers

from sklearn import preprocessing
from sklearn import model_selection

from transformers import AdamW
from transformers import AdamW,get_linear_schedule_with_warmup

def get_device():
  if torch.cuda.is_available():
    return torch.device('cuda:0')
  else:
    return torch.device('cpu')

class EntiyDataset:
  def __init__(self,texts,pos,tags):
    self.texts=texts
    self.pos=pos
    self.tags=tags

  def __len__(self):
    return len(self.texts)

  def __getitem__(self,item):
    text = self.texts[item]
    pos = self.pos[item]
    tags = self.tags[item]
    ids=[]
    target_pos=[]
    target_tag=[]
    
    for i,s in enumerate(text):
      inputs=config.TOKENIZER.encode(
          s,
          add_special_tokens=False,

      )
      input_len=len(inputs)
      ids.extend(inputs)
      target_pos.extend([pos[i]]* input_len)
      target_tag.extend([tags[i]]* input_len)

      ids=[101]+ids+[102]
      target_pos=[0]+target_pos+[0]
      target_tag=[0]+target_tag+[0]

      mask=[1]*len(ids)
      token_type_ids=[0]*len(ids)

      padding_len=config.MAX_LEN-len(ids)


      ids=ids+([0]* padding_len)
      mask=mask+([0]* padding_len)
      token_type_ids=token_type_ids+([0]* padding_len)
      target_pos=target_pos+([0]* padding_len)
      target_tag=target_tag+([0]* padding_len)

      return{
        'ids':torch.tensor(ids,dtype=torch.long),
        'mask':torch.tensor(mask,dtype=torch.long),
        'token_type_ids':torch.tensor(token_type_ids,dtype=torch.long),

        'target_pos':torch.tensor(target_pos,dtype=torch.long),
        'target_tag':torch.tensor(target_tag,dtype=torch.long),
      }

def train_fn(data_loader,model,optimizer,device,scheduler):
  model.train()
  final_loss=0

  for data in tqdm(data_loader,total=len(data_loader)):
    for k ,v in data.items():
      data[k].to(device)
    optimizer.zero_grad()
    _,_,loss=model(**data)
    loss.backward()
    optimizer.step()
    scheduler.step()
    final_loss+=loss.item()
  return final_loss/len(data_loader)

def eval_fn(data_loader,model,device):
  model.eval()
  final_loss=0
  for data in tqdm(data_loader,total=len(data_loader)):
    for k ,v in data.tems():
      data[k].to(device)
    loss=model(**data)
    final_loss+=loss.item()
  return final_loss/len(data_loader)

def loss_fn(output,target,mask,num_labels):
  lfn=nn.CrossEntropyLoss()
  active_loss=mask.view(-1)==1
  active_logits=output.view(-1,num_labels)

  active_labels=torch.where(
      active_loss,
      target.view(-1),
      torch.tensor(lfn.ignore_index).type_as(target)
  )
  loss=lfn(active_logits,active_labels)
  return loss

class EntityModel(nn.Module):
  def __init__(self,num_tag,num_pos):
    super(EntityModel,self).__init__()
    self.num_tag=num_tag
    self.num_pos=num_pos
    self.bert=transformers.BertModel.from_pretrained(config.BASE_MODEL_PATH,return_dict=True)
    self.bert_drop_1=nn.Dropout(0.3)
    self.bert_drop_2=nn.Dropout(0.3)
    self.out_tag=nn.Linear(768,self.num_tag)
    self.out_pos=nn.Linear(768,self.num_pos)
    

  def forward(self,ids,mask,token_type_ids,target_pos,target_tag):
    output=self.bert(ids,attention_mask=mask,token_type_ids=token_type_ids)
    o_tag=self.bert_drop_1(output.last_hidden_state)
    o_pos=self.bert_drop_2(output.last_hidden_state)

    tag =self.out_tag(o_tag)
    pos =self.out_pos(o_pos)

    loss_tag=loss_fn(tag,target_tag,mask,self.num_tag)
    loss_pos=loss_fn(pos,target_pos,mask,self.num_pos)

    loss=(loss_tag+loss_pos)/2

    return tag,pos,loss

def process_data():
  data_path=data_directory()
  df=pd.read_csv(data_path['train_data_path'],encoding='latin-1')
  df['Sentence #'].fillna(method='ffill',inplace=True,axis=0)

  enc_pos=preprocessing.LabelEncoder()
  enc_tag=preprocessing.LabelEncoder()

  df.POS=enc_pos.fit_transform(df.POS)
  df.Tag=enc_tag.fit_transform(df.Tag)

  sentences=df.groupby('Sentence #')['Word'].apply(list).values
  pos=df.groupby('Sentence #')['POS'].apply(list).values
  tag=df.groupby('Sentence #')['Tag'].apply(list).values

  return sentences,pos,tag,enc_pos,enc_tag

if __name__=='__main__':
  sentences,pos,tag,enc_pos,enc_tag=process_data()
  meta_data={
      'enc_pos':enc_pos,
      'enc_tag':enc_tag
  }
  num_pos=len(list(enc_pos.classes_))
  num_tag=len(list(enc_tag.classes_))

  joblib.dump(meta_data,'meta.bin')
  
  #split stentence
  (train_sentences,test_sentences,train_pos,test_pos,train_tag,test_tag)=model_selection.train_test_split(sentences,pos,tag,random_state=42,test_size=0.1)

  # create Datatset

  Train_dataset=EntiyDataset(
                              texts=train_sentences,
                              pos=train_pos,
                              tags=train_tag)
  Test_dataset=EntiyDataset(
                              texts=test_sentences,
                              pos=test_pos,
                              tags=test_tag)
  

  # create Dataloader

  train_data_loader=torch.utils.data.DataLoader(
                                                  Train_dataset,
                                                  batch_size=config.TRAIN_BATCH_SIZE)
  test_data_loader=torch.utils.data.DataLoader(
                                                  Test_dataset,
                                                  batch_size=config.TEST_BATCH_SIZE)

  device=get_device()
  model=EntityModel(num_tag=num_tag, num_pos=num_pos)
  model.to(device)

  parameters_opt=list(model.named_parameters())
  no_decay=['bias','LayerNorm.bias','LayerNorm.weight']
  optimizer_parametrs=[{
                        'params':[parameters for name,parameters in parameters_opt if not any(nd in name for nd in no_decay)],
                        'weight_decay':0.001},
                       {
                        'params':[parameters for name,parameters in parameters_opt if any(nd in name for nd in no_decay)],
                        'weight_decay':0.0
                       }]
  num_train_steps=int(len(Train_dataset)/config.TRAIN_BATCH_SIZE * config.EPOCHS)
  optimizer=AdamW(optimizer_parametrs,lr=3e-5)
  scheduler=get_linear_schedule_with_warmup(
                                            optimizer,
                                            num_warmup_steps=0,
                                            num_training_steps=num_train_steps
  )
  best_loss=np.inf
  for epoch in range(config.EPOCHS):
    train_loss=train_fn(train_data_loader,model,optimizer,device,scheduler)
    test_loss=eval_fn(test_data_loader,model,device)
    print(f'Train Loss: {train_loss}')
    print(f'Test Loss: {test_loss}')
    if (test_loss < best_loss):
      torch.save(model.state_dict(),config.MODEL_PATH)
      best_loss=test_loss

