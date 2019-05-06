/*
 * Cozmonaut
 * Copyright 2019 The Cozmonaut Contributors
 */

#ifndef GLOBAL_H
#define GLOBAL_H

/** Global program info. */
struct global {
  /** The cmdline argument count. */
  int argc;

  /** The cmdline argument vector. */
  const char** argv;
};

/** An immutable view of global program info. */
extern const struct global* const g;

/** A mutable view of  global program info. */
extern struct global* const g_mut;

#endif // #ifndef GLOBAL_H
