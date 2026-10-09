package org.mario64mod.s3airbuilder;

import android.Manifest;
import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.util.Base64;
import android.util.Log;
import android.webkit.ConsoleMessage;
import android.webkit.JavascriptInterface;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import java.io.File;
import java.io.FileOutputStream;
import java.io.OutputStream;

/**
 * Hosts the mod builder page (assets/index.html) in a WebView.
 * The page does all the work; this class only provides the ROM file picker and saving the result.
 */
public class MainActivity extends Activity
{
	private static final String TAG = "Mario64Builder";
	private static final int REQUEST_ROM = 1;
	private static final int REQUEST_SAVE = 2;
	private static final int REQUEST_PERMISSION = 3;
	private static final String S3AIR_MODS_FOLDER = "Android/data/org.eukaryot.sonic3air/files/mods";

	private WebView webView;
	private ValueCallback<Uri[]> fileCallback;
	private byte[] pendingData;
	private String pendingName;

	@Override
	protected void onCreate(Bundle savedInstanceState)
	{
		super.onCreate(savedInstanceState);
		webView = new WebView(this);
		setContentView(webView);

		WebSettings settings = webView.getSettings();
		settings.setJavaScriptEnabled(true);
		settings.setDomStorageEnabled(true);
		settings.setAllowFileAccess(true);

		webView.setWebViewClient(new WebViewClient()
		{
			@Override
			public boolean shouldOverrideUrlLoading(WebView view, String url)
			{
				return true;		// The page has no links to follow
			}
		});

		webView.setWebChromeClient(new WebChromeClient()
		{
			@Override
			public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback, FileChooserParams params)
			{
				if (fileCallback != null)
					fileCallback.onReceiveValue(null);
				fileCallback = callback;
				Intent intent = new Intent(Intent.ACTION_GET_CONTENT);
				intent.addCategory(Intent.CATEGORY_OPENABLE);
				intent.setType("*/*");
				try
				{
					startActivityForResult(Intent.createChooser(intent, "Choose your Super Mario 64 ROM"), REQUEST_ROM);
				}
				catch (ActivityNotFoundException e)
				{
					fileCallback = null;
					return false;
				}
				return true;
			}

			@Override
			public boolean onConsoleMessage(ConsoleMessage message)
			{
				Log.i(TAG, message.message());
				return true;
			}
		});

		webView.addJavascriptInterface(new Bridge(), "MarioBuilderApp");
		if (savedInstanceState != null)
			webView.restoreState(savedInstanceState);
		else
			webView.loadUrl("file:///android_asset/index.html");
	}

	@Override
	protected void onSaveInstanceState(Bundle outState)
	{
		super.onSaveInstanceState(outState);
		webView.saveState(outState);
	}

	@Override
	protected void onActivityResult(int requestCode, int resultCode, Intent data)
	{
		Uri uri = (resultCode == RESULT_OK && data != null) ? data.getData() : null;
		if (requestCode == REQUEST_ROM)
		{
			if (fileCallback != null)
				fileCallback.onReceiveValue(uri != null ? new Uri[] { uri } : null);
			fileCallback = null;
		}
		else if (requestCode == REQUEST_SAVE)
		{
			if (uri == null)
			{
				report(false, "Not saved.");
				return;
			}
			try
			{
				OutputStream out = getContentResolver().openOutputStream(uri);
				out.write(pendingData);
				out.close();
				report(true, "Saved " + pendingName + ".");
			}
			catch (Exception e)
			{
				report(false, "Saving failed: " + e.getMessage());
			}
		}
		else
		{
			super.onActivityResult(requestCode, resultCode, data);
		}
	}

	@Override
	public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults)
	{
		if (requestCode != REQUEST_PERMISSION)
			return;
		if (grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED)
			installPending();
		else
			report(false, "No permission to access the storage. Use \"Save Mario64.zip\" instead.");
	}

	@Override
	public void onBackPressed()
	{
		if (webView.canGoBack())
			webView.goBack();
		else
			super.onBackPressed();
	}

	private void report(final boolean ok, final String message)
	{
		runOnUiThread(new Runnable()
		{
			@Override
			public void run()
			{
				String js = "window.onSaveResult && window.onSaveResult(" + ok + ", " + jsString(message) + ")";
				webView.evaluateJavascript(js, null);
			}
		});
	}

	private static String jsString(String s)
	{
		StringBuilder b = new StringBuilder("\"");
		for (char c : s.toCharArray())
		{
			if (c == '"' || c == '\\')
				b.append('\\').append(c);
			else if (c < 0x20)
				b.append(String.format("\\u%04x", (int)c));
			else
				b.append(c);
		}
		return b.append('"').toString();
	}

	// Android 10 and older: write the mod straight into the Sonic 3 A.I.R. mods folder
	private void installPending()
	{
		try
		{
			File base = new File(Environment.getExternalStorageDirectory(), "Android/data/org.eukaryot.sonic3air/files");
			if (!base.isDirectory())
			{
				report(false, "Sonic 3 A.I.R. folder not found. Start the game once, then try again - or use \"Save Mario64.zip\".");
				return;
			}
			File mods = new File(Environment.getExternalStorageDirectory(), S3AIR_MODS_FOLDER);
			mods.mkdirs();
			FileOutputStream out = new FileOutputStream(new File(mods, pendingName));
			out.write(pendingData);
			out.close();
			report(true, "Installed into " + S3AIR_MODS_FOLDER + ". Now enable \"Mario 64\" in the game's Mods menu.");
		}
		catch (Exception e)
		{
			report(false, "Installing failed: " + e.getMessage() + "\nUse \"Save Mario64.zip\" instead.");
		}
	}

	/** Functions the page can call (window.MarioBuilderApp) */
	private class Bridge
	{
		@JavascriptInterface
		public boolean canInstallDirectly()
		{
			// Since Android 11, apps can't write into other apps' folders under Android/data
			return Build.VERSION.SDK_INT <= 29;
		}

		@JavascriptInterface
		public void saveFile(String name, String base64)
		{
			pendingName = name;
			pendingData = Base64.decode(base64, Base64.DEFAULT);
			runOnUiThread(new Runnable()
			{
				@Override
				public void run()
				{
					Intent intent = new Intent(Intent.ACTION_CREATE_DOCUMENT);
					intent.addCategory(Intent.CATEGORY_OPENABLE);
					intent.setType("application/zip");
					intent.putExtra(Intent.EXTRA_TITLE, pendingName);
					try
					{
						startActivityForResult(intent, REQUEST_SAVE);
					}
					catch (ActivityNotFoundException e)
					{
						saveToAppFolder();
					}
				}
			});
		}

		@JavascriptInterface
		public void installDirectly(String name, String base64)
		{
			pendingName = name;
			pendingData = Base64.decode(base64, Base64.DEFAULT);
			runOnUiThread(new Runnable()
			{
				@Override
				public void run()
				{
					if (Build.VERSION.SDK_INT >= 23 && checkSelfPermission(Manifest.permission.WRITE_EXTERNAL_STORAGE) != PackageManager.PERMISSION_GRANTED)
						requestPermissions(new String[] { Manifest.permission.WRITE_EXTERNAL_STORAGE }, REQUEST_PERMISSION);
					else
						installPending();
				}
			});
		}
	}

	// Fallback without a document picker
	private void saveToAppFolder()
	{
		try
		{
			File dir = getExternalFilesDir(null);
			File file = new File(dir, pendingName);
			FileOutputStream out = new FileOutputStream(file);
			out.write(pendingData);
			out.close();
			report(true, "Saved to " + file.getAbsolutePath());
		}
		catch (Exception e)
		{
			report(false, "Saving failed: " + e.getMessage());
		}
	}
}
