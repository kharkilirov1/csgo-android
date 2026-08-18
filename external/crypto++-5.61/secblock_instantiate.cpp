// Explicit instantiation of the Crypto++ SecBlock allocators the engine links
// against (SecByteBlock and SecBlock<word32>, used by engine/net_ws.cpp).
//
// The engine builds a curated subset of Crypto++ that omits dll.cpp, the unit
// which normally provides these instantiations. secblock.h declares them as
// `extern template class`, and clang/lld honor that by NOT instantiating them
// implicitly at the use sites - so without this unit their allocate/deallocate/
// reallocate members are undefined at link time. (GCC was more lenient, which
// is why the older armv7a/GCC build did not need it.)
//
// Only the two specializations actually referenced are instantiated here, to
// avoid clashing with any other translation unit that may instantiate the rest.

#include "secblock.h"

namespace CryptoPP {

template class AllocatorWithCleanup<byte,   false>; // AllocatorWithCleanup<unsigned char>
template class AllocatorWithCleanup<word32, false>; // AllocatorWithCleanup<unsigned int>

} // namespace CryptoPP
