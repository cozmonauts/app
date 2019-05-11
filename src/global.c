/*
 * Cozmonaut
 * Copyright 2019 The Cozmonaut Contributors
 */

#include "global.h"

/** The global program info. */
static struct global g__;

// Prepare an immutable view
const struct global* const g = &g__;

// Prepare a mutable view
struct global* const g_mut = &g__;
