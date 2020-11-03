import transformers

MAX_LEN=128
TRAIN_BATCH_SIZE=16
TEST_BATCH_SIZE=4
EPOCHS=10
BASE_MODEL_PATH='bert-base-uncased'
VOCAB_PATH='/content/vocab.txt'
MODEL_PATH='model.bin'
TOKENIZER=transformers.BertTokenizer.from_pretrained('bert-base-uncased',do_lower_case=True)

