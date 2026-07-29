#ifndef GOOGLE_PROTOBUF_ATOMICOPS_INTERNALS_GCC_ATOMIC_H_
#define GOOGLE_PROTOBUF_ATOMICOPS_INTERNALS_GCC_ATOMIC_H_

namespace google {
namespace protobuf {
namespace internal {

#define GOOGLE_PROTOBUF_ATOMICOPS_IMPL(Type) \
inline Type NoBarrier_CompareAndSwap(volatile Type* p, Type oldv, Type newv) { __atomic_compare_exchange_n(p, &oldv, newv, false, __ATOMIC_RELAXED, __ATOMIC_RELAXED); return oldv; } \
inline Type NoBarrier_AtomicExchange(volatile Type* p, Type v) { return __atomic_exchange_n(p, v, __ATOMIC_RELAXED); } \
inline Type NoBarrier_AtomicIncrement(volatile Type* p, Type v) { return __atomic_add_fetch(p, v, __ATOMIC_RELAXED); } \
inline Type Barrier_AtomicIncrement(volatile Type* p, Type v) { return __atomic_add_fetch(p, v, __ATOMIC_SEQ_CST); } \
inline Type Acquire_CompareAndSwap(volatile Type* p, Type oldv, Type newv) { __atomic_compare_exchange_n(p, &oldv, newv, false, __ATOMIC_ACQUIRE, __ATOMIC_ACQUIRE); return oldv; } \
inline Type Release_CompareAndSwap(volatile Type* p, Type oldv, Type newv) { __atomic_compare_exchange_n(p, &oldv, newv, false, __ATOMIC_RELEASE, __ATOMIC_RELAXED); return oldv; } \
inline void NoBarrier_Store(volatile Type* p, Type v) { __atomic_store_n(p, v, __ATOMIC_RELAXED); } \
inline void Acquire_Store(volatile Type* p, Type v) { __atomic_store_n(p, v, __ATOMIC_SEQ_CST); } \
inline void Release_Store(volatile Type* p, Type v) { __atomic_store_n(p, v, __ATOMIC_RELEASE); } \
inline Type NoBarrier_Load(volatile const Type* p) { return __atomic_load_n(p, __ATOMIC_RELAXED); } \
inline Type Acquire_Load(volatile const Type* p) { return __atomic_load_n(p, __ATOMIC_ACQUIRE); } \
inline Type Release_Load(volatile const Type* p) { return __atomic_load_n(p, __ATOMIC_SEQ_CST); }

GOOGLE_PROTOBUF_ATOMICOPS_IMPL(Atomic32)
GOOGLE_PROTOBUF_ATOMICOPS_IMPL(Atomic64)

#undef GOOGLE_PROTOBUF_ATOMICOPS_IMPL

inline void MemoryBarrier() { __atomic_thread_fence(__ATOMIC_SEQ_CST); }

}  // namespace internal
}  // namespace protobuf
}  // namespace google

#endif
