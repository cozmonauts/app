/*
 * Cozmonaut
 * Copyright 2019 The Cozmonaut Contributors
 */

#define LOG_TAG "service"

#include <stdlib.h>

#include "log.h"
#include "service.h"

struct service_state {
  /** Nonzero iff started. */
  int started;
};

int service_load(struct service* svc) {
  LOGT("Loading {}", _str(svc->name));

  // If service has allocated state, ...
  if (svc->state) {
    // ... then it is already loaded
    LOGE("Already loaded {}", _str(svc->name));
    return 1;
  }

  // Allocate service state
  svc->state = malloc(sizeof(struct service_state));
  svc->state->started = 0;

  // Call back to service
  if (svc->iface) {
    int code;
    if (code = svc->iface->on_load()) {
      LOGW("{} on_load() returned code {}", _str(svc->name), _i(code));
    }
  }

  LOGI("Loaded {}", _str(svc->name));
  return 0;
}

int service_unload(struct service* svc) {
  LOGT("Unloading {}", _str(svc->name));

  // If service does NOT have allocated state, ...
  if (!svc->state) {
    // ... then it is NOT already loaded
    LOGE("Not loaded {}", _str(svc->name));
    return 1;
  }

  // Call back to service
  if (svc->iface) {
    int code;
    if (code = svc->iface->on_unload()) {
      LOGW("{} on_unload() returned code {}", _str(svc->name), _i(code));
    }
  }

  // Deallocate service state
  free(svc->state);

  LOGI("Unloaded {}", _str(svc->name));
  return 0;
}

int service_start(struct service* svc) {
  LOGT("Starting {}", _str(svc->name));

  // If service does NOT have allocated state, ...
  if (!svc->state) {
    // ... then it is NOT already loaded
    LOGE("Not loaded {}", _str(svc->name));
    return 1;
  }

  // If service is already started
  if (svc->state->started) {
    LOGE("Already started {}", _str(svc->name));
    return 1;
  }

  // Set started flag
  svc->state->started = 1;

  // Call back to service
  if (svc->iface) {
    int code;
    if (code = svc->iface->on_start()) {
      LOGW("{} on_start() returned code {}", _str(svc->name), _i(code));
    }
  }

  LOGI("Started {}", _str(svc->name));
  LOGI("{}", _str(svc->description));
  return 0;
}

int service_stop(struct service* svc) {
  LOGT("Stopping {}", _str(svc->name));

  // If service does NOT have allocated state, ...
  if (!svc->state) {
    // ... then it is NOT already loaded
    LOGE("Not loaded {}", _str(svc->name));
    return 1;
  }

  // If service is not already started
  if (!svc->state->started) {
    LOGE("Not started {}", _str(svc->name));
    return 1;
  }

  // Call back to service
  if (svc->iface) {
    int code;
    if (code = svc->iface->on_stop()) {
      LOGW("{} on_stop() returned code {}", _str(svc->name), _i(code));
    }
  }

  // Clear started flag
  svc->state->started = 0;

  LOGI("Stopped {}", _str(svc->name));
  return 0;
}

int service_call(struct service* svc, int fn, const void* a, void* b) {
  // If service does NOT have allocated state, ...
  if (!svc->state) {
    // ... then it is NOT already loaded
    LOGE("Not loaded {}", _str(svc->name));
    return 1;
  }

  // If service is not already started
  if (!svc->state->started) {
    LOGE("Not started {}", _str(svc->name));
    return 1;
  }

  if (svc->iface) {
    // Get the actual procedure
    int (* proc)(const void*, void*) = svc->iface->proc(fn);

    // And call it
    int code;
    if (code = proc(a, b)) {
      LOGW("{} proc #{} returned code {}", _str(svc->name), _i(fn), _i(code));
    }
  }

  return 0;
}
