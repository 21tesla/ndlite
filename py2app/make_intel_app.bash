cd ..
set -e 

if [ -d "build" ]; then
    echo "Cleaning up old build directory..."
    rm -r build
fi

if [ -d "dist" ]; then
    echo "Cleaning up old dist directory..."
    rm -r dist
fi

echo "Starting py2app build..."

# Workaround for py2app/setuptools conflict with pyproject.toml
if [ -f "pyproject.toml" ]; then
    mv pyproject.toml pyproject.toml.bak
fi

python py2app/setup_intel.py py2app

if [ -f "pyproject.toml.bak" ]; then
    mv pyproject.toml.bak pyproject.toml
fi

xattr -cr dist/ndlite.app

echo "Stripping old signatures..."
find dist/ndlite.app -type f \( -name "*.dylib" -o -name "*.so" -o -name "*.a" -o -name "*.bundle" \) -exec codesign --remove-signature {} \; 2>/dev/null
codesign --remove-signature dist/ndlite.app/Contents/MacOS/ndlite 2>/dev/null
codesign --remove-signature dist/ndlite.app 2>/dev/null


echo "Signing internal libraries..."
find dist/ndlite.app -type f \( -name "*.dylib" -o -name "*.so" -o -name "*.a" -o -name "*.bundle" \) -exec codesign --force --verify --verbose --options runtime --timestamp --sign "Developer ID Application: logan Donaldson (E76H6A445J)" {} \;


echo "Signing bundled Python interpreter..."
if [ -f "dist/ndlite.app/Contents/MacOS/python" ]; then
    codesign --force --verify --verbose --options runtime --timestamp \
    --sign "Developer ID Application: logan Donaldson (E76H6A445J)" \
    dist/ndlite.app/Contents/MacOS/python
fi


echo "Signing versions-A..."
find dist/ndlite.app -path "*/Versions/A/*" -type f -exec codesign --force --verify --verbose --timestamp --options runtime --sign "Developer ID Application: logan Donaldson (E76H6A445J)"  --team-id "E76H6A445J" {} \;



echo "Signing main executable..."
codesign --force --verify --verbose --options runtime --timestamp --entitlements py2app/entitlements.plist --sign "Developer ID Application: logan Donaldson (E76H6A445J)" dist/ndlite.app/Contents/MacOS/ndlite


echo "Sealing the bundle..."
codesign --force --verify --verbose --options runtime --timestamp --entitlements py2app/entitlements.plist --sign "Developer ID Application: logan Donaldson (E76H6A445J)" dist/ndlite.app


echo "Running strict validation..."
codesign -vvv --deep --strict dist/ndlite.app


echo "making zip file"
rm -rf dist/ndlite_intel.zip
ditto -c -k --keepParent dist/ndlite.app dist/ndlite_intel.zip


echo "submitting to apple"
xcrun notarytool submit dist/ndlite_intel.zip  --apple-id "logand@yorku.ca"  --team-id "E76H6A445J" --password "jpgh-inpm-expa-ypfy"  --wait

echo "stapling the app"
xcrun stapler staple dist/ndlite.app

echo "checking master credentials"
spctl -a -t exec -vv dist/ndlite.app

# Define variables
APP_NAME="ndlite"
BUILD_DIR="dist"
STAGING_DIR="dmg_staging"
BG_IMAGE="icons/background1.jpg"
OUTPUT_DMG="ndlite_intel.dmg"

# 1. Prepare a clean staging directory
echo "Preparing staging directory..."
rm -rf "${STAGING_DIR}"
mkdir -p "${STAGING_DIR}"
cp -R "${BUILD_DIR}/${APP_NAME}.app" "${STAGING_DIR}/"

# 2. Clean up previous DMG if it exists to prevent creation errors
rm -f "${OUTPUT_DMG}"

# 3. Run create-dmg
create-dmg \
  --volname "${APP_NAME} Installer" \
  --volicon "${BUILD_DIR}/${APP_NAME}.app/Contents/Resources/app_icon.icns" \
  --background "${BG_IMAGE}" \
  --window-pos 800 600 \
  --window-size 800 600 \
  --icon-size 100 \
  --icon "${APP_NAME}.app" 200 300 \
  --hide-extension "${APP_NAME}.app" \
  --app-drop-link 600 300 \
  "${OUTPUT_DMG}" \
  "${STAGING_DIR}"

# 4. Optional: Clean up the temporary staging directory afterward
rm -rf "${STAGING_DIR}"

