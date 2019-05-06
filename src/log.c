/*
 * Cozmonaut
 * Copyright 2019 The Cozmonaut Contributors
 */

#include <stdio.h>
#include "log.h"

extern void log__temp_format_and_submit(struct log_form* form);

void log__submit_form(struct log_form* form) {
  log__temp_format_and_submit(form); // TODO: Log to a MPSC ring buffer
}
