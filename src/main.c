/*
 * Cozmonaut
 * Copyright 2019 The Cozmonaut Contributors
 */

#include <stdio.h>
#include <stdlib.h>

#include <linenoise.h>

int main() {
  char* line;
  while ((line = linenoise("C:\\> ")) != NULL) {
    if (line[0] != '\0') {
      printf("echo: %s\n", line);
    }
    free(line);
  }
}
