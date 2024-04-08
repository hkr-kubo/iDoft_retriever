import os
import argparse
import re
import matplotlib.pyplot as plt
import numpy as np

parser = argparse.ArgumentParser()
parser.add_argument("-i", "--input", help="Filepath of input folder")
args = parser.parse_args()


def main():
    modified_lines = np.zeros(175)
    files = os.listdir(args.input)
    for file in files:
        with open(f"{args.input}{file}", "r") as f:
            modify, addition, deletion = 0, 0, 0
            for line in f:
                block = re.search(r"^@@", line)
                addition += len(re.findall(r"^\+", line))
                deletion += len(re.findall(r"^-", line))
                if block != None:
                    modify += max(addition, deletion)
                    addition, deletion = 0, 0
            modify += max(addition, deletion)
            modified_lines[modify] += 1
    left = np.arange(175)
    fig, ax = plt.subplots()
    plt.bar(left, modified_lines)
    ax.set_xlabel("Lines of modification")
    ax.set_ylabel("Number of tests")
    plt.show()


if __name__ == "__main__":
    main()
