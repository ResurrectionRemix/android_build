blue='\033[0;34m'
cyan='\033[0;36m'
yellow='\033[0;33m'
red='\033[0;31m'
nocol='\033[0m'
cd out/target/product/sprout4/
cp boot.img ../../../../build/48c/
cd ../../../../build/48c/
if [ ! -e boot.img ]
then
 echo Error! Stop.
 exit
fi
chmod a+x extract-kernel.pl
chmod a+x extract-ramdisk.pl
./extract-kernel.pl boot.img 2>/dev/null
./extract-ramdisk.pl boot.img 2>/dev/null
cd boot.img-ramdisk
rm init.sprout.rc
rm fstab.sprout
cd ..
cp prop/* boot.img-ramdisk/
base_dir=`pwd`
working_folder=`pwd`
#compile_mkboot
cd mkboot
mkbootimg_src=mkbootimg_mt65xx.c
mkbootimg_out=mkbootimg
mkbootfs_file=mkbootfs
mkbootimg_file=mkbootimg_out
gcc -o mkbootfs mkbootfs.c
if [ -e $mkbootimg_file ]
then
rm -rf $mkbootimg_file
fi
gcc -c rsa.c
gcc -c sha.c
gcc rsa.o sha.o mkbootimg_mt65xx.c -w -o $mkbootimg_out
cd ..
cp mkboot/mkbootimg mkbootimg
cp mkboot/$mkbootfs_file $mkbootfs_file
./$mkbootfs_file boot.img-ramdisk | gzip > ramdisk.gz
base_temp=`od -A n -h -j 14 -N 2 boot.img | sed 's/ //g'`
zeros=0000
base=0x$base_temp$zeros
temp=`od -A n -H -j 20 -N 4 boot.img | sed 's/ //g'`
ramdisk_load_addr=0x$temp
ramdisk_addr=ramdisk_load_addr
mkdir -p old_boot
mv boot.img old_boot/boot.img
ramdisk_params=""
./mkbootimg --kernel zImage --ramdisk ramdisk.gz -o boot.img --base $base $ramdisk_params
if [ -e boot.img ]
then
echo "------------------------------------------------------------------------"
fi
cd ../../out/target/product/sprout4/
KEYWORD_PATTERN='ota'
KEYWORD_PATTERN=ota
mkdir $KEYWORD_PATTERN
cp *.zip $KEYWORD_PATTERN/
cd $KEYWORD_PATTERN
grep -Ew -q "KEYWORD_PATTERN" *.zip
KEYWORD=$(grep -Ew -o "$KEYWORD_PATTERN" *.zip | head -1)
rm -rf $KEYWORD
clear
unzip *.zip
rm *.zip
rm boot.img
cd ../../../../../build/48c
cp boot.img ../../out/target/product/sprout4/$KEYWORD_PATTERN/
cd ../../out/target/product/sprout4/$KEYWORD_PATTERN
zip -r sprout8_ROM.zip * 
cd ..
mkdir -p Sprout8
echo -e "$blue Installing zip file!"
mv ota/sprout8_ROM.zip Sprout8/
rm -rf ota/
echo "Success! ROM file at out/target/product/sprout4/Sprout8/sprout8_zip"
