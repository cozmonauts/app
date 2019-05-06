/*
 * Cozmonaut
 * Copyright 2019 The Cozmonaut Contributors
 */

#define LOG_TAG "console"

#include <pthread.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include <linenoise.h>

#include "console.h"

#include "../log.h"
#include "../service.h"

/** The console thread. */
static pthread_t console__thread;

/** The console loop kill switch. */
static volatile int console__loop_kill;

/** The console interrupted flag. */
static volatile int console__interrupted;

/** The soliciting flag. */
static volatile int console__soliciting;

/**
 * SIGINT handler.
 *
 * @param na Not used
 */
static void console__sigint(int na) {
  // Set interrupted flag
  console__interrupted = 1;
}

/**
 * Handle a single input.
 *
 * @param input The input string
 */
static void console__handle_input(const char* input) {
  if (!strcmp("stop", input)) {
    // Set interrupt flag
    console__interrupted = 1;
  }
}

/**
 * Main function for the console thread.
 *
 * @param arg Not used
 * @return Not used
 */
static void* console__thread_main(void* arg) {
  char* line;
  do {
    // Issue next prompt
    // This is a blocking call
    line = linenoise("> ");

    // Skip empty strings
    if (line[0] == '\0') {
      continue;
    }

    // Handle the line as independent input
    console__handle_input(line);

    // Free the line
    free(line);
  } while (1);
}

//
// Service Procedures
//

static int console__proc_interrupted(const void* a, void* b) {
  int* out_interrupted = b;
  *out_interrupted = console__interrupted;
  console__interrupted = 0;
  return 0;
}

static int console__proc_solicit(const void* a, void* b) {
  const char* prompt = a;
  char** out_result = b;
  return 0;
}

//
// Service Callbacks
//

static int on_load() {
  // Handle SIGINT for our purposes
  signal(SIGINT, &console__sigint);

  return 0;
}

static int on_unload() {
  // Restore SIGINT to default handling
  signal(SIGINT, SIG_DFL);

  return 0;
}

static int on_start() {
  // Spawn the console thread
  pthread_create(&console__thread, NULL, &console__thread_main, NULL);

  return 0;
}

static int on_stop() {
  // Cancel the console thread
  // There is no clean way to break it
  pthread_cancel(console__thread);

  // Wait for console thread to die
  pthread_join(console__thread, NULL);

  return 0;
}

static int (* proc(int fn))(const void* a, void* b) {
  switch (fn) {
    case service_console_fn_interrupted:
      return &console__proc_interrupted;
    case service_console_fn_solicit:
      return &console__proc_solicit;
  }

  return NULL;
}

static struct service_iface iface = {
  .on_load = &on_load,
  .on_unload = &on_unload,
  .on_start = &on_start,
  .on_stop = &on_stop,
  .proc = &proc,
};

struct service* const SERVICE_CONSOLE = &(struct service) {
  .name = "console",
  .description = "The console service manages the console user interface (CUI).",
  .iface = &iface,
};
