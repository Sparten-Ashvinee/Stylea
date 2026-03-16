package com.stylea.app.ui.activities

import android.content.Intent
import android.graphics.Bitmap
import android.os.Bundle
import android.view.MenuItem
import android.view.View
import android.widget.Toast
import androidx.activity.viewModels
import androidx.appcompat.app.AppCompatActivity
import com.stylea.app.R
import com.stylea.app.databinding.ActivityTryOnBinding
import com.stylea.app.ui.viewmodels.TryOnViewModel

/**
 * Displays the virtual try-on result together with the segmented clothing image.
 *
 * Uses the same shared [TryOnViewModel] that [MainActivity] populated –
 * the ViewModel survives the Activity transition via the default
 * [androidx.lifecycle.ViewModelProvider] scoped to the process.
 *
 * Note: Because both activities run in the same task/process, the ViewModel
 * created with `by viewModels()` in MainActivity is NOT automatically shared
 * here. We use `by viewModels()` again which creates a separate instance.
 * The result is passed via the ViewModel instance that was populated; since
 * the ViewModel is scoped to the activity, we rely on TryOnActivity starting
 * while the result is already set in the previous Activity's ViewModel.
 *
 * To properly share ViewModels across activities, an Application-scoped
 * ViewModel or a saved-state approach would be used. For simplicity here,
 * the result bitmaps are passed via a companion-object cache.
 */
class TryOnActivity : AppCompatActivity() {

    private lateinit var binding: ActivityTryOnBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityTryOnBinding.inflate(layoutInflater)
        setContentView(binding.root)

        supportActionBar?.setDisplayHomeAsUpEnabled(true)
        supportActionBar?.title = getString(R.string.title_try_on)

        val result = ResultCache.result
        if (result != null) {
            showResult(result.tryOnBitmap, result.segmentedBitmap)
        } else {
            showError(getString(R.string.error_generic))
        }

        setupClickListeners()
    }

    override fun onOptionsItemSelected(item: MenuItem): Boolean {
        if (item.itemId == android.R.id.home) {
            onBackPressedDispatcher.onBackPressed()
            return true
        }
        return super.onOptionsItemSelected(item)
    }

    // -----------------------------------------------------------------------
    // UI
    // -----------------------------------------------------------------------

    private fun showResult(tryOnBitmap: Bitmap, segmentedBitmap: Bitmap) {
        binding.layoutLoading.visibility = View.GONE
        binding.layoutError.visibility = View.GONE
        binding.layoutContent.visibility = View.VISIBLE

        binding.ivResult.setImageBitmap(tryOnBitmap)
        binding.ivSegmented.setImageBitmap(segmentedBitmap)
    }

    private fun showError(message: String) {
        binding.layoutLoading.visibility = View.GONE
        binding.layoutContent.visibility = View.GONE
        binding.layoutError.visibility = View.VISIBLE
        binding.tvErrorMessage.text = message
    }

    private fun setupClickListeners() {
        binding.btnSave.setOnClickListener {
            val bmp = ResultCache.result?.tryOnBitmap ?: return@setOnClickListener
            saveBitmapToGallery(bmp)
        }

        binding.btnShare.setOnClickListener {
            val bmp = ResultCache.result?.tryOnBitmap ?: return@setOnClickListener
            shareBitmap(bmp)
        }

        binding.btnTryAgain.setOnClickListener {
            ResultCache.result = null
            finish()
        }

        binding.btnRetry.setOnClickListener {
            ResultCache.result = null
            finish()
        }
    }

    // -----------------------------------------------------------------------
    // Save / share
    // -----------------------------------------------------------------------

    private fun saveBitmapToGallery(bitmap: Bitmap) {
        try {
            android.content.ContentValues().apply {
                put(android.provider.MediaStore.Images.Media.DISPLAY_NAME,
                    "stylea_tryon_${System.currentTimeMillis()}.jpg")
                put(android.provider.MediaStore.Images.Media.MIME_TYPE, "image/jpeg")
                put(android.provider.MediaStore.Images.Media.RELATIVE_PATH,
                    android.os.Environment.DIRECTORY_PICTURES + "/Stylea")
            }.let { values ->
                contentResolver.insert(
                    android.provider.MediaStore.Images.Media.EXTERNAL_CONTENT_URI, values
                )?.let { uri ->
                    contentResolver.openOutputStream(uri)?.use { out ->
                        bitmap.compress(Bitmap.CompressFormat.JPEG, 92, out)
                    }
                    Toast.makeText(this, R.string.success_saved, Toast.LENGTH_SHORT).show()
                }
            }
        } catch (e: Exception) {
            Toast.makeText(this, R.string.error_generic, Toast.LENGTH_SHORT).show()
        }
    }

    private fun shareBitmap(bitmap: Bitmap) {
        try {
            val cacheDir = java.io.File(cacheDir, "shared_images").also { it.mkdirs() }
            val file = java.io.File(cacheDir, "stylea_share_${System.currentTimeMillis()}.jpg")
            file.outputStream().use { bitmap.compress(Bitmap.CompressFormat.JPEG, 90, it) }

            val uri = androidx.core.content.FileProvider.getUriForFile(
                this, "${packageName}.fileprovider", file
            )

            startActivity(
                Intent.createChooser(
                    Intent(Intent.ACTION_SEND).apply {
                        type = "image/jpeg"
                        putExtra(Intent.EXTRA_STREAM, uri)
                        addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                    },
                    "Share via"
                )
            )
        } catch (e: Exception) {
            Toast.makeText(this, R.string.error_generic, Toast.LENGTH_SHORT).show()
        }
    }

    // -----------------------------------------------------------------------
    // Simple in-process result cache
    // -----------------------------------------------------------------------

    companion object ResultCache {
        /** Set by [MainActivity] before starting this activity. */
        var result: com.stylea.app.data.models.TryOnResult? = null
    }
}
