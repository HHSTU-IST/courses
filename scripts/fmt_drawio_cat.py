import os


def merge_files(infile, mode="h", style_file="drawio-tree.txt"):
    if mode == "h":
        styline = "# layout: horizontalflow"
    elif mode == "v":
        styline = "# layout: verticalflow"
    else:
        print("Unknown mode")

    infile_path = os.path.abspath(infile)
    outfile_path = infile_path.replace(".csv", ".txt")
    with open(outfile_path, "w") as outfile:
        with open(style_file) as f:
            outfile.writelines(f)
            outfile.write(styline)
            outfile.write("\n")
            outfile.write("# csv data below:\n")
        with open(infile) as f:
            outfile.writelines(f)


# Usage:
infile = "drawio.csv"
merge_files(infile)
