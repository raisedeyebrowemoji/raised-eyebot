import os

def generate_file_tree(path, prefix=""):
    """Recursively generates a file tree from the given path."""
    if not os.path.exists(path):
        return "The specified path does not exist."

    if os.path.isfile(path):
        return prefix + "╚ " + os.path.basename(path)

    tree = []
    contents = sorted(os.listdir(path))
    for i, item in enumerate(contents):
        item_path = os.path.join(path, item)
        if os.path.isdir(item_path):
            tree.append(prefix + "╟ " + item)
            if i == len(contents) - 1:
                tree.append(generate_file_tree(item_path, prefix + "   "))
            else:
                tree.append(generate_file_tree(item_path, prefix + "║   "))
        else:
            if i == len(contents) - 1:
                tree.append(prefix + "╚ " + item)
            else:
                tree.append(prefix + "╟ " + item)
    return "\n".join(tree)