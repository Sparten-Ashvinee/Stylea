package com.stylea.app.ui.viewmodels

import android.app.Application
import android.content.ContentValues
import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.net.Uri
import android.os.Environment
import android.provider.MediaStore
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.LiveData
import androidx.lifecycle.MutableLiveData
import androidx.lifecycle.viewModelScope
import com.stylea.app.BuildConfig
import com.stylea.app.data.api.ApiException
import com.stylea.app.data.api.StyleaApiClient
import com.stylea.app.data.models.TryOnResult
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.ByteArrayOutputStream
import java.io.File

/**
 * ViewModel for image selection and AI try-on flow.
 *
 * Holds selected image URIs, orchestrates the backend calls, and exposes
 * [UiState] LiveData consumed by [MainActivity].
 *
 * When the try-on succeeds, [MainActivity] stores the result in
 * [TryOnActivity.ResultCache] before starting [TryOnActivity].
 */
class TryOnViewModel(application: Application) : AndroidViewModel(application) {

    // -----------------------------------------------------------------------
    // Sealed state
    // -----------------------------------------------------------------------

    sealed class UiState {
        object Idle : UiState()
        object SegmentingClothing : UiState()
        object GeneratingTryOn : UiState()
        data class Success(val result: TryOnResult) : UiState()
        data class Error(val message: String) : UiState()
    }

    // -----------------------------------------------------------------------
    // Exposed LiveData
    // -----------------------------------------------------------------------

    private val _uiState = MutableLiveData<UiState>(UiState.Idle)
    val uiState: LiveData<UiState> = _uiState

    private val _fashionUri = MutableLiveData<Uri?>()
    val fashionUri: LiveData<Uri?> = _fashionUri

    private val _personUri = MutableLiveData<Uri?>()
    val personUri: LiveData<Uri?> = _personUri

    private val _saveEvent = MutableLiveData<Boolean>()
    val saveEvent: LiveData<Boolean> = _saveEvent

    // -----------------------------------------------------------------------
    // Internal state
    // -----------------------------------------------------------------------

    private val apiClient = StyleaApiClient(BuildConfig.BACKEND_URL)

    // -----------------------------------------------------------------------
    // Public methods
    // -----------------------------------------------------------------------

    fun setFashionUri(uri: Uri) {
        _fashionUri.value = uri
        resetIfError()
    }

    fun setPersonUri(uri: Uri) {
        _personUri.value = uri
        resetIfError()
    }

    /**
     * Runs the full pipeline:
     * 1. Segment clothing from fashion image (POST /segment)
     * 2. Apply try-on (POST /tryon)
     */
    fun startTryOn() {
        val fashionUri = _fashionUri.value ?: run {
            _uiState.value = UiState.Error("Please select a fashion image.")
            return
        }
        val personUri = _personUri.value ?: run {
            _uiState.value = UiState.Error("Please select your photo.")
            return
        }

        viewModelScope.launch {
            runCatching {
                val ctx = getApplication<Application>()

                // --- Step 1: Segment ---
                _uiState.value = UiState.SegmentingClothing
                val fashionFile = withContext(Dispatchers.IO) { uriToTempFile(ctx, fashionUri, "fashion") }
                val segmentedBytes = withContext(Dispatchers.IO) { apiClient.segment(fashionFile) }
                val segmentedBitmap = BitmapFactory.decodeByteArray(segmentedBytes, 0, segmentedBytes.size)
                    ?: error("Failed to decode segmented image")

                // --- Step 2: Try-on ---
                _uiState.value = UiState.GeneratingTryOn
                val personFile = withContext(Dispatchers.IO) { uriToTempFile(ctx, personUri, "person") }
                val tryOnBytes = withContext(Dispatchers.IO) { apiClient.tryOn(personFile, fashionFile) }
                val tryOnBitmap = BitmapFactory.decodeByteArray(tryOnBytes, 0, tryOnBytes.size)
                    ?: error("Failed to decode try-on image")

                TryOnResult(tryOnBitmap = tryOnBitmap, segmentedBitmap = segmentedBitmap)
            }.onSuccess { result ->
                _uiState.value = UiState.Success(result)
            }.onFailure { ex ->
                _uiState.value = UiState.Error(friendlyMessage(ex))
            }
        }
    }

    /**
     * Save the try-on result bitmap to the device gallery.
     */
    fun saveResultToGallery(bitmap: Bitmap) {
        viewModelScope.launch {
            runCatching {
                withContext(Dispatchers.IO) {
                    saveBitmapToGallery(getApplication(), bitmap)
                }
            }.onSuccess {
                _saveEvent.value = true
            }.onFailure {
                _saveEvent.value = false
            }
        }
    }

    fun resetState() {
        _uiState.value = UiState.Idle
    }

    // -----------------------------------------------------------------------
    // Private helpers
    // -----------------------------------------------------------------------

    private fun resetIfError() {
        if (_uiState.value is UiState.Error) {
            _uiState.value = UiState.Idle
        }
    }

    private fun uriToTempFile(context: Context, uri: Uri, prefix: String): File {
        val inputStream = context.contentResolver.openInputStream(uri)
            ?: error("Cannot open URI: $uri")
        val bitmap = BitmapFactory.decodeStream(inputStream)
        inputStream.close()

        val file = File.createTempFile(prefix, ".jpg", context.cacheDir)
        file.outputStream().use { out ->
            val bos = ByteArrayOutputStream()
            bitmap.compress(Bitmap.CompressFormat.JPEG, 90, bos)
            out.write(bos.toByteArray())
        }
        return file
    }

    private fun saveBitmapToGallery(context: Context, bitmap: Bitmap) {
        val values = ContentValues().apply {
            put(MediaStore.Images.Media.DISPLAY_NAME, "stylea_tryon_${System.currentTimeMillis()}.jpg")
            put(MediaStore.Images.Media.MIME_TYPE, "image/jpeg")
            put(MediaStore.Images.Media.RELATIVE_PATH, Environment.DIRECTORY_PICTURES + "/Stylea")
        }
        val uri = context.contentResolver.insert(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, values)
            ?: error("MediaStore insert failed")
        context.contentResolver.openOutputStream(uri)?.use { out ->
            bitmap.compress(Bitmap.CompressFormat.JPEG, 92, out)
        }
    }

    private fun friendlyMessage(ex: Throwable): String = when (ex) {
        is ApiException -> when {
            ex.httpCode in 500..599 -> "Server error (${ex.httpCode}). Please try again."
            ex.httpCode == 503 -> "AI model not ready. Is the backend running?"
            else -> ex.message ?: "Unknown API error"
        }
        is java.net.ConnectException,
        is java.net.SocketTimeoutException -> "Cannot reach the server. Please check your connection."
        else -> ex.message ?: "An unexpected error occurred."
    }
}
