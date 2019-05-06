/*
 * Cozmonaut
 * Copyright 2019 The Cozmonaut Contributors
 */

#ifndef SERVICE_H
#define SERVICE_H

struct service_iface;
struct service_state;

/** A service definition. */
struct service {
  /** The service name. */
  const char* name;

  /** The service description. */
  const char* description;

  /** The service interface. */
  struct service_iface* iface;

  /** The service state. */
  struct service_state* state;
};

/** A service interface. */
struct service_iface {
  /**
   * Called when the service first loads.
   *
   * @return Zero on success, otherwise nonzero
   */
  int (* on_load)();

  /**
   * Called when the service finally unloads.
   *
   * @return Zero on success, otherwise nonzero
   */
  int (* on_unload)();

  /**
   * Called when the service starts up.
   *
   * @return Zero on success, otherwise nonzero
   */
  int (* on_start)();

  /**
   * Called when the service shuts down.
   *
   * @return Zero on success, otherwise nonzero
   */
  int (* on_stop)();

  /**
   * Get the procedure for a service function.
   *
   * This abomination of function pointer syntax is equal to:
   *   typedef int (* myfunc)(const void* a, void* b)
   *   myfunc (* proc)(int fn)
   *
   * @param fn The function ordinal
   * @return The function pointer
   */
  int (* (* proc)(int fn))(const void* a, void* b);
};

/**
 * Load a service.
 *
 * @param svc The service definition
 * @return Zero on success, otherwise nonzero
 */
int service_load(struct service* svc);

/**
 * Unload a service.
 *
 * @param svc The service definition
 * @return Zero on success, otherwise nonzero
 */
int service_unload(struct service* svc);

/**
 * Start a service.
 *
 * @param svc The service definition
 * @return Zero on success, otherwise nonzero
 */
int service_start(struct service* svc);

/**
 * Stop a service.
 *
 * @param svc The service definition
 * @return Zero on success, otherwise nonzero
 */
int service_stop(struct service* svc);

/**
 * Call a service.
 *
 * @param svc The service definition
 * @param fn The function ordinal
 * @param a An immutable argument
 * @param b A mutable argument
 * @return Zero on success, otherwise nonzero
 */
int service_call(struct service* svc, int fn, const void* a, void* b);

#endif // #ifndef SERVICE_H
