
import json

def main():
  with open("cephVolumes.json") as f:
    data = json.load(f)

  size_sum = 0

  for entry in data:
    size = entry["bytes_used"]
    path = entry["path"]
    size_sum += size
    if size > 1024*1024*1024*100:
      print(f"Found entry with {size=} and {path=}")
  print(f"{size_sum = }")

if __name__ == "__main__":
  main()
