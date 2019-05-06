#
# Cozmonaut
# Copyright 2019 The Cozmonaut Contributors
#

import time

from .operation.interact import OperationInteract, InteractMode


def main():
    args = {
        'ser-a': '0241c714',
        'ser-b': '45a18821',
        'mode': 'both',
    }

    op = OperationInteract(args)
    op.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass

    op.stop()


if __name__ == '__main__':
    main()
