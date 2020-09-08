import argparse

import torch
import torch.nn as nn
from sklearn.metrics import accuracy_score
from torch.optim import Adam
from torch.utils.data import DataLoader
from tqdm import tqdm

import constants
from slp.config import SPECIAL_TOKENS
from slp.data.collators import Sequence2SequenceCollator
from slp.data.spelling import SpellCorrectorDataset
from slp.data.transforms import CharacterTokenizer
from slp.modules.convs2s import Seq2Seq
from slp.util.parallel import DataParallelCriterion, DataParallelModel

DEBUG = False


config = {
    "device": "cuda",
    "parallel": True,
    "num_workers": 4,
    "batch_size": 300,
    "lr": 1e-3,
    "epochs": 10,
    "hidden_size": 256,
    "embedding_size": 256,
    "encoder_kernel_size": 5,
    "decoder_kernel_size": 5,
    "encoder_layers": 10,
    "decoder_layers": 10,
    "encoder_dropout": 0.2,
    "decoder_dropout": 0.2,
    "max_length": 256,
    "gradient_clip": 0.1,
    # "teacher_forcing": 0.4,
}


if DEBUG:
    config["device"] = "cpu"
    config["batch_size"] = 128
    config["parallel"] = False
    config["num_workers"] = 0


def parse_args():
    parser = argparse.ArgumentParser("Train spell checker")
    parser.add_argument("--train", type=str, help="Train split file")
    parser.add_argument("--val", type=str, help="Validation split file")
    args = parser.parse_args()

    return args


collate_fn = Sequence2SequenceCollator(device="cpu")


def train_epoch(model, optimizer, criterion, train_loader, device="cpu", parallel=True):
    model = model.train()
    avg_loss, nbatch = 0, len(train_loader)
    n_correct, n_tokens = 0.0, 0.0
    clip = config["gradient_clip"]

    for bxi, batch in enumerate(tqdm(train_loader), 1):
        optimizer.zero_grad()

        source, target, _ = map(lambda x: x.to(device), batch)
        decoded = model(source, target[:, :-1])
        target = target[:, 1:]

        if parallel:
            loss = criterion(
                [d.contiguous().view(-1, d.size(-1)) for d in decoded],
                target.contiguous().view(-1),
            )
            loss = loss.mean()
            gathered = nn.parallel.gather(decoded, "cuda:0")
        else:
            loss = criterion(
                decoded.contiguous().view(-1, decoded.size(-1)),
                target.contiguous().view(-1),
            )
            gathered = decoded

        dec_tok = gathered.argmax(-1)
        y_hat, y = dec_tok[target != 0].view(-1), target[target != 0].view(-1)
        n_correct += (y_hat == y).sum()
        n_tokens += len(y_hat)
        avg_loss += loss.item()

        if bxi % 100 == 0:
            print(
                "Train iteration: {} \t Loss: {} \t Acc: {}".format(
                    bxi, avg_loss / bxi, n_correct / n_tokens
                )
            )

        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), clip)
        optimizer.step()
    avg_loss = avg_loss / nbatch

    return avg_loss


def eval_epoch(model, criterion, val_loader, device="cpu", parallel=True):
    model = model.eval()
    avg_loss, nbatch = 0, len(val_loader)
    n_correct, n_tokens = 0.0, 0.0
    with torch.no_grad():
        for batch in tqdm(val_loader):
            source, target, _ = map(lambda x: x.to(device), batch)
            decoded = model(source, target[:, :-1])
            target = target[:, 1:]

            if parallel:
                loss = criterion(
                    [d.contiguous().view(-1, d.size(-1)) for d in decoded],
                    target.contiguous().view(-1),
                )
                loss = loss.mean()
                gathered = nn.parallel.gather(decoded, "cuda:0")
            else:
                loss = criterion(
                    decoded.contiguous().view(-1, decoded.size(-1)),
                    target.contiguous().view(-1),
                )
                gathered = decoded
            dec_tok = gathered.argmax(-1)
            y_hat, y = dec_tok[target != 0].view(-1), target[target != 0].view(-1)
            n_correct += (y_hat == y).sum()
            n_tokens += len(y_hat)
            avg_loss += loss.item()
        avg_loss = avg_loss / nbatch
        accuracy = n_correct / n_tokens

    return avg_loss, accuracy


def train(
    model,
    optimizer,
    criterion,
    train_loader,
    val_loader,
    epochs=50,
    device="cpu",
    parallel=True,
):
    for e in range(epochs):
        _ = train_epoch(
            model, optimizer, criterion, train_loader, device=device, parallel=parallel
        )
        train_loss, train_acc = eval_epoch(
            model, criterion, train_loader, device=device, parallel=parallel
        )
        print(
            "Epoch: {}\tTrain loss: {}\tTrain accuracy: {}".format(
                e, train_loss, train_acc
            )
        )
        val_loss, val_acc = eval_epoch(
            model, criterion, val_loader, device=device, parallel=parallel
        )
        print("Epoch: {}\tVal loss: {}\tVal accuracy: {}".format(e, val_loss, val_acc))
        torch.save(model.state_dict(), "spell_check.model.{}.pth".format(e))
        torch.save(optimizer.state_dict(), "spell_check.opt.{}.pth".format(e))


if __name__ == "__main__":
    args = parse_args()

    if DEBUG:
        args.train = "hnc.test"
        args.val = "hnc.test"
    tokenizer = CharacterTokenizer(
        constants.CHARACTER_VOCAB,
        prepend_bos=True,
        append_eos=True,
        specials=SPECIAL_TOKENS,
    )

    sos_idx = tokenizer.c2i[SPECIAL_TOKENS.BOS.value]
    pad_idx = tokenizer.c2i[SPECIAL_TOKENS.PAD.value]
    eos_idx = tokenizer.c2i[SPECIAL_TOKENS.EOS.value]

    vocab_size = len(tokenizer.vocab)

    trainset = SpellCorrectorDataset(args.train, tokenizer=tokenizer)
    valset = SpellCorrectorDataset(args.val, tokenizer=tokenizer)

    train_loader = DataLoader(
        trainset,
        batch_size=config["batch_size"],
        num_workers=config["num_workers"],
        pin_memory=True,
        shuffle=True,
        collate_fn=collate_fn,
        drop_last=True,
    )
    val_loader = DataLoader(
        valset,
        batch_size=config["batch_size"],
        num_workers=config["num_workers"],
        pin_memory=True,
        shuffle=True,
        collate_fn=collate_fn,
        drop_last=True,
    )

    model = Seq2Seq(
        vocab_size,
        vocab_size,
        hidden_size=config["hidden_size"],
        embedding_size=config["embedding_size"],
        encoder_layers=config["encoder_layers"],
        decoder_layers=config["decoder_layers"],
        encoder_kernel_size=config["encoder_kernel_size"],
        decoder_kernel_size=config["decoder_kernel_size"],
        encoder_dropout=config["encoder_dropout"],
        decoder_dropout=config["decoder_dropout"],
        max_length=config["max_length"],
        device=config["device"],
        pad_idx=pad_idx,
        # teacher_forcing_p=config["teacher_forcing"],
    )

    optimizer = Adam(
        [p for p in model.parameters() if p.requires_grad], lr=config["lr"]
    )

    criterion = nn.CrossEntropyLoss(ignore_index=0)

    if config["parallel"]:
        model = DataParallelModel(model)
        criterion = DataParallelCriterion(criterion)
    model = model.to(config["device"])
    criterion = criterion.to(config["device"])

    train(
        model,
        optimizer,
        criterion,
        train_loader,
        val_loader,
        epochs=config["epochs"],
        device=config["device"],
        parallel=config["parallel"],
    )
