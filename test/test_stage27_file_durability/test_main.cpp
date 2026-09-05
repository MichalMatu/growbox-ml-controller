#include "climate/storage/Stage27FileDurability.h"

#include <cassert>
#include <cstdio>
#include <cstring>
#include <sys/stat.h>
#include <unistd.h>

using namespace growbox::app::climate_io::storage;

int main() {
  char path[]="/tmp/growbox-durable-XXXXXX";
  const int fd=mkstemp(path);
  assert(fd>=0);
  std::FILE* file=fdopen(fd,"w+");
  assert(file!=nullptr);
  constexpr char payload[]="durable-record\n";
  assert(std::fwrite(payload,1U,sizeof(payload)-1U,file)==sizeof(payload)-1U);
  const auto result=stage27FlushSyncAndStat(file);
  assert(result.ok);
  assert(result.failed_step==Stage27FileDurabilityStep::None);
  assert(result.size_bytes==sizeof(payload)-1U);
  struct stat st{};
  assert(::stat(path,&st)==0);
  assert(static_cast<std::size_t>(st.st_size)==sizeof(payload)-1U);
  std::fclose(file);
  assert(::unlink(path)==0);

  const auto invalid=stage27FlushSyncAndStat(nullptr);
  assert(!invalid.ok);
  assert(invalid.failed_step==Stage27FileDurabilityStep::Descriptor);
  return 0;
}
